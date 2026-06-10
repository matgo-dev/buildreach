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
import { QuantityInput } from "@/components/mall/QuantityInput";
import { ApiError } from "@/lib/api";
import {
  getCart,
  updateCartItem,
  removeCartItem,
  type CartItemPublic,
  type CartPublic,
} from "@/lib/api/cart";
import { getProduct, type ProductPublicDetail, type PriceTier } from "@/lib/api/products";
import { useCartStore } from "@/stores/cartStore";
import { formatCurrency } from "@/lib/formatters";

// ---------- 参考价：按 product_id 批量拉商品详情拿阶梯价 ----------

function useProductDetails(productIds: number[]) {
  // 用稳定的 key（排序后的 id 列表）做单次 SWR 请求
  const sortedIds = useMemo(
    () => [...productIds].sort((a, b) => a - b),
    [productIds],
  );
  const swrKey = sortedIds.length > 0 ? `cart-products-${sortedIds.join(",")}` : null;

  const { data } = useSWR<Map<number, ProductPublicDetail>>(
    swrKey,
    async () => {
      const results = new Map<number, ProductPublicDetail>();
      // 并行请求，失败的跳过
      const settled = await Promise.allSettled(
        sortedIds.map((pid) => getProduct(pid)),
      );
      for (let i = 0; i < settled.length; i++) {
        const r = settled[i];
        if (r.status === "fulfilled") results.set(sortedIds[i], r.value);
      }
      return results;
    },
    { revalidateOnFocus: false, dedupingInterval: 60000 },
  );

  return data ?? new Map<number, ProductPublicDetail>();
}

function getSkuTiers(
  productMap: Map<number, ProductPublicDetail>,
  productId: number,
  skuId: number,
): PriceTier[] {
  const product = productMap.get(productId);
  if (!product) return [];
  const sku = product.skus.find((s) => s.id === skuId);
  return sku?.price_tiers ?? [];
}

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

  // 参考价：拉商品详情
  const productIds = useMemo(() => {
    const ids = new Set<number>();
    (cart?.items ?? []).forEach((i) => { if (i.is_purchasable) ids.add(i.product_id); });
    return Array.from(ids);
  }, [cart]);

  const productMap = useProductDetails(productIds);

  // 修改数量（debounce）
  const debounceRef = useMemo(() => new Map<number, NodeJS.Timeout>(), []);

  const handleQuantityChange = useCallback(
    (itemId: number, qty: number) => {
      // 乐观更新本地
      mutate(
        (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            items: prev.items.map((i) =>
              i.item_id === itemId ? { ...i, quantity: qty } : i
            ),
          };
        },
        { revalidate: false },
      );

      // debounce 调后端
      const existing = debounceRef.get(itemId);
      if (existing) clearTimeout(existing);
      debounceRef.set(
        itemId,
        setTimeout(async () => {
          debounceRef.delete(itemId);
          try {
            const updated = await updateCartItem(itemId, qty);
            syncFromCart(updated);
            mutate(updated, { revalidate: false });
          } catch (err) {
            // 回滚：重新拉取
            mutate();
            if (err instanceof ApiError && err.messageKey) {
              const key = err.messageKey.replace(/^error\./, "");
              try { toast.error(tError(key)); } catch { toast.error(err.message); }
            }
          }
        }, 500),
      );
    },
    [mutate, syncFromCart, debounceRef, toast, tError],
  );

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

  // 提交询价
  const handleSubmitInquiry = useCallback(() => {
    const ids = Array.from(checkedIds);
    if (ids.length === 0) return;
    router.push(`/${locale}/buyer/rfqs/create?source=cart&items=${ids.join(",")}`);
  }, [checkedIds, router, locale]);

  // ---- 渲染 ----

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0D4D4D]" />
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
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#0D4D4D] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d]"
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
                  className="h-4 w-4 rounded border-gray-300 text-[#0D4D4D] focus:ring-[#0D4D4D]"
                />
              </th>
              <th className="px-4 py-3 font-medium">{t("productInfo")}</th>
              <th className="px-4 py-3 font-medium">{t("referencePrice")}</th>
              <th className="px-4 py-3 font-medium">{t("quantity")}</th>
              <th className="w-14 px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const tiers = getSkuTiers(productMap, item.product_id, item.sku_id);
              const product = productMap.get(item.product_id);
              const unit = product?.unit ?? "PCS";
              const unavailable = !item.is_purchasable;
              const checked = checkedIds.has(item.item_id);
              const specParts = item.sku_name
                ? [item.sku_name, item.sku_code].filter(Boolean).join(" · ")
                : [item.sku_code, item.color, item.material, item.manufacturer_model].filter(Boolean).join(" · ");
              const sortedTiers = [...tiers].sort((a, b) => a.min_qty - b.min_qty);

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
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-[#0D4D4D] focus:ring-[#0D4D4D] disabled:opacity-40"
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
                        {item.moq != null && (
                          <p className="mt-1 text-[11px] text-gray-400">
                            MOQ: {item.moq}
                          </p>
                        )}
                        {unavailable && item.unavailable_reason && (
                          <span className="mt-1 inline-block rounded bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600">
                            {t(`unavailable_${item.unavailable_reason}` as Parameters<typeof t>[0])}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* 参考价 */}
                  <td className="px-4 py-3 align-top">
                    {!unavailable && sortedTiers.length > 0 ? (
                      <div className="space-y-0.5 text-xs text-gray-500">
                        {sortedTiers.map((tier) => {
                          const range = tier.max_qty
                            ? `${tier.min_qty}-${tier.max_qty}`
                            : `${tier.min_qty}+`;
                          return (
                            <div key={tier.id}>
                              <span className="text-gray-400">{range}</span>{" "}
                              <span className="font-semibold text-[#0D4D4D]">
                                {formatCurrency(tier.unit_price, tier.currency, locale, {
                                  maximumFractionDigits: 2,
                                })}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-300">—</span>
                    )}
                  </td>

                  {/* 数量 */}
                  <td className="px-4 py-3 align-top">
                    {!unavailable ? (
                      <QuantityInput
                        value={item.quantity}
                        onChange={(qty) => handleQuantityChange(item.item_id, qty)}
                        moq={item.moq ?? 1}
                        unit={unit}
                      />
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
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-colors ${
            checkedIds.size > 0
              ? "bg-[#0D4D4D] text-white hover:bg-[#0a3d3d]"
              : "bg-gray-200 text-gray-400 cursor-not-allowed"
          }`}
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
