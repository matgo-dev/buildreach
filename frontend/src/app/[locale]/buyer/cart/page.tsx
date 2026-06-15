"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import {
  Loader2,
  ShoppingCart,
  Trash2,
  ArrowRight,
  PackageOpen,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { ApiError } from "@/lib/api";
import {
  getCart,
  removeCartItem,
  type CartItemPublic,
  type CartPublic,
} from "@/lib/api/cart";
import { useCartStore } from "@/stores/cartStore";

// ---------- 主页面 ----------

function CartContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("cart");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const refreshFlag = useCartStore((s) => s.refreshFlag);
  const triggerRefresh = useCartStore((s) => s.triggerRefresh);

  // 询价篮数据
  const { data: cart, isLoading, mutate } = useSWR<CartPublic>(
    `cart-page-${refreshFlag}`,
    () => getCart(),
    { revalidateOnFocus: false },
  );

  // 同步 count
  useEffect(() => {
    if (cart) syncFromCart(cart);
  }, [cart, syncFromCart]);

  // 勾选状态
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());

  // 询价篮变化时清除已不存在的勾选项
  useEffect(() => {
    if (!cart) return;
    const validIds = new Set(cart.items.map((i) => i.item_id));
    setCheckedIds((prev) => {
      const next = new Set<number>();
      prev.forEach((id) => { if (validIds.has(id)) next.add(id); });
      return next;
    });
  }, [cart]);

  const purchasableItems = useMemo(
    () => (cart?.items ?? []).filter((i) => i.is_purchasable),
    [cart],
  );

  const allChecked =
    purchasableItems.length > 0 &&
    purchasableItems.every((i) => checkedIds.has(i.item_id));

  const handleToggleAll = useCallback(() => {
    if (allChecked) {
      setCheckedIds(new Set());
    } else {
      setCheckedIds(new Set(purchasableItems.map((i) => i.item_id)));
    }
  }, [allChecked, purchasableItems]);

  const handleCheck = useCallback((itemId: number, checked: boolean) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(itemId); else next.delete(itemId);
      return next;
    });
  }, []);

  // 删除单项
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteConfirm = useCallback(async () => {
    if (deleteTarget === null) return;
    setDeleting(true);
    try {
      const updated = await removeCartItem(deleteTarget);
      syncFromCart(updated);
      mutate(updated, { revalidate: false });
      triggerRefresh();
      setDeleteTarget(null);
    } catch (err) {
      mutate();
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, syncFromCart, mutate, triggerRefresh, toast, tError]);

  // 批量删除选中
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [batchDeleting, setBatchDeleting] = useState(false);

  const handleBatchDelete = useCallback(async () => {
    const ids = Array.from(checkedIds);
    if (ids.length === 0) return;
    setBatchDeleting(true);
    let failed = 0;
    for (const id of ids) {
      try {
        await removeCartItem(id);
      } catch {
        failed++;
      }
    }
    // 重新拉取最新数据
    const updated = await getCart();
    syncFromCart(updated);
    mutate(updated, { revalidate: false });
    triggerRefresh();
    setCheckedIds(new Set());
    setBatchDeleteOpen(false);
    setBatchDeleting(false);
    if (failed > 0) {
      toast.warning(t("deletePartialFail", { failed }));
    }
  }, [checkedIds, syncFromCart, mutate, triggerRefresh, toast, t]);

  // 提交询价：跳转到询价创建页，带上选中的 item_id
  const handleSubmitInquiry = useCallback(() => {
    const ids = Array.from(checkedIds);
    if (ids.length === 0) return;
    router.push(`/${locale}/buyer/rfqs/create?items=${ids.join(",")}`);
  }, [checkedIds, router, locale]);

  // ---- 渲染 ----

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#00505a]" />
      </div>
    );
  }

  const items = cart?.items ?? [];

  // 空状态
  if (items.length === 0) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-gray-200 bg-white">
        <ShoppingCart className="mb-4 h-16 w-16 text-gray-200" />
        <h2 className="text-lg font-semibold text-gray-600">{t("empty")}</h2>
        <button
          type="button"
          onClick={() => router.push(`/${locale}/mall`)}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#00505a] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#003f46]"
        >
          {t("goToMall")}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 页标题 + 操作栏 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">
          {t("title")}
          <span className="ml-2 text-base font-normal text-gray-400">
            ({t("itemCount", { count: items.length })})
          </span>
        </h1>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-slate-50 text-left text-xs text-gray-500">
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={handleToggleAll}
                  disabled={purchasableItems.length === 0}
                  className="h-4 w-4 rounded border-gray-300 text-[#00505a] focus:ring-[#00505a]"
                />
              </th>
              <th className="px-4 py-3 font-medium">{t("productInfo")}</th>
              <th className="px-4 py-3 font-medium">{t("quantity")}</th>
              <th className="w-14 px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const unavailable = !item.is_purchasable;
              const checked = checkedIds.has(item.item_id);
              const specParts = item.variant_display ?? "\u2014";

              return (
                <tr
                  key={item.item_id}
                  className={`border-t border-gray-100 transition-colors ${
                    unavailable ? "opacity-50" : "even:bg-slate-50/50 hover:bg-blue-50/50"
                  }`}
                >
                  {/* 勾选 */}
                  <td className="px-4 py-3 align-top">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={unavailable}
                      onChange={(e) => handleCheck(item.item_id, e.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-[#00505a] focus:ring-[#00505a] disabled:opacity-40"
                    />
                  </td>

                  {/* 商品信息：图片 + 名称 + 规格 */}
                  <td className="px-4 py-3">
                    <div className="flex items-start gap-3">
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-gray-200 bg-gray-50">
                        {item.main_image ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={item.main_image} alt="" className="h-full w-full object-contain" />
                        ) : (
                          <div className="flex h-full items-center justify-center text-gray-300">
                            <PackageOpen className="h-6 w-6" />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-gray-800">
                          {item.product_name ?? "—"}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-gray-500">{specParts}</p>
                        {unavailable && item.unavailable_reason && (
                          <span className="mt-1 inline-block rounded bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600">
                            {t(`unavailable_${item.unavailable_reason}` as Parameters<typeof t>[0])}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* 数量（只读展示） */}
                  <td className="px-4 py-3 align-top">
                    {!unavailable ? (
                      <span className="text-sm font-semibold text-gray-700">{item.quantity}</span>
                    ) : (
                      <span className="text-sm text-gray-400">—</span>
                    )}
                  </td>

                  {/* 删除 */}
                  <td className="px-4 py-3 align-top text-center">
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(item.item_id)}
                      className="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 已选提示 + 批量删除 */}
      {checkedIds.size > 0 && (
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <span>{t("selected", { count: checkedIds.size })}</span>
          <button
            type="button"
            onClick={() => setBatchDeleteOpen(true)}
            className="text-red-500 transition-colors hover:text-red-700"
          >
            {t("deleteSelected")}
          </button>
        </div>
      )}

      {/* 底部操作栏 */}
      <div className="sticky bottom-0 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-6 py-4 shadow-sm">
        <span className="text-sm text-gray-600">
          {t("selected", { count: checkedIds.size })}
        </span>
        <button
          type="button"
          disabled={checkedIds.size === 0}
          onClick={handleSubmitInquiry}
          className="inline-flex items-center gap-2 rounded-lg bg-[#00505a] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#003d45] disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed"
        >
          {t("submitInquiry")}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {/* 删除单项确认框 */}
      <ConfirmModal
        open={deleteTarget !== null}
        title={t("confirmDelete")}
        variant="danger"
        confirmLabel={tCommon("confirm")}
        cancelLabel={tCommon("cancel")}
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* 批量删除确认框 */}
      <ConfirmModal
        open={batchDeleteOpen}
        title={t("confirmDeleteSelected", { count: checkedIds.size })}
        variant="danger"
        confirmLabel={tCommon("confirm")}
        cancelLabel={tCommon("cancel")}
        loading={batchDeleting}
        onConfirm={handleBatchDelete}
        onCancel={() => setBatchDeleteOpen(false)}
      />
    </div>
  );
}

export default function CartPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.CART_READ]}>
      <CartContent />
    </RouteGuard>
  );
}
