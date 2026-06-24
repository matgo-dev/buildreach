"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import {
  Loader2,
  ShoppingCart,
  Trash2,
  ArrowRight,
  PackageOpen,
  ChevronDown,
  ChevronUp,
  MessageCircle,
} from "lucide-react";
import { RfqTabNav } from "@/components/rfq/RfqTabNav";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { ApiError } from "@/lib/api";
import {
  getCart,
  removeCartItem,
  updateCartItem,
  type CartItemPublic,
  type CartPublic,
} from "@/lib/api/cart";
import { getProduct, type AttrItem } from "@/lib/api/products";
import { useCartStore } from "@/stores/cartStore";
import { useWhatsApp } from "@/hooks/useWhatsApp";

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
  const wa = useWhatsApp();

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

  // 变体编辑
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  // productId -> 可选属性轴列表（已筛出 selectable=true）
  const [productAttrs, setProductAttrs] = useState<Record<number, AttrItem[]>>({});
  const [editingVariants, setEditingVariants] = useState<Array<{ attr_name: string; value: string }>>([]);
  const [variantSaving, setVariantSaving] = useState(false);

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

  return (
    <div className="space-y-4">
      {/* Tab + 内容整体卡片 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {/* Tab 导航：询价篮 / 询价管理 — 始终显示 */}
        <RfqTabNav />

        {/* 空状态 */}
        {items.length === 0 ? (
          <div className="flex min-h-[400px] flex-col items-center justify-center">
            <ShoppingCart className="mb-4 h-16 w-16 text-gray-200" />
            <h2 className="text-lg font-semibold text-gray-600">{t("empty")}</h2>
            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push(`/${locale}/mall`)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#00505a] bg-[#00505a] px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d]"
              >
                {t("goToMall")}
                <ArrowRight className="h-4 w-4" />
              </button>
              {wa.configured && (
                <a
                  href={wa.link!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-full border border-whatsapp bg-whatsapp px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-whatsapp/90"
                >
                  <MessageCircle className="h-4 w-4" />
                  {t("inquireNow")}
                </a>
              )}
            </div>
          </div>
        ) : (
          <>

        {/* 表头 */}
        <div className="flex items-center gap-3 border-b border-gray-200 bg-slate-50 px-5 py-3 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={allChecked}
            onChange={handleToggleAll}
            disabled={purchasableItems.length === 0}
            className="h-4 w-4 shrink-0 rounded border-gray-300 text-[#00505a] focus:ring-[#00505a]"
          />
          <span className="flex-1 font-medium">{t("productInfo")}</span>
          <span className="w-20 text-center font-medium">{t("quantity")}</span>
          <span className="w-10" />
        </div>

        {/* 行项 */}
        <div className="divide-y divide-gray-100">
          {items.map((item) => {
            const unavailable = !item.is_purchasable;
            const checked = checkedIds.has(item.item_id);
            const detailHref = `/${locale}/mall/products/${item.product_id}`;
            // 交期文案
            const leadTime =
              item.lead_time_min && item.lead_time_max
                ? `${item.lead_time_min}-${item.lead_time_max} ${t("days")}`
                : item.lead_time_min
                  ? `${item.lead_time_min}+ ${t("days")}`
                  : null;

            return (
              <div key={item.item_id}>
              <div
                className={`flex items-start gap-4 px-5 py-4 transition-colors ${
                  unavailable ? "opacity-50 bg-gray-50/50" : "hover:bg-blue-50/30"
                }`}
              >
                {/* 勾选 */}
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={unavailable}
                  onChange={(e) => handleCheck(item.item_id, e.target.checked)}
                  className="mt-3 h-4 w-4 shrink-0 rounded border-gray-300 text-[#00505a] focus:ring-[#00505a] disabled:opacity-40"
                />

                {/* 商品图片 — 可点击跳转详情 */}
                <a href={detailHref} className="h-[88px] w-[88px] shrink-0 overflow-hidden rounded-lg border border-gray-200 bg-gray-50 hover:border-[#00505a] transition-colors">
                  {item.main_image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={item.main_image} alt="" className="h-full w-full object-contain" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-gray-300">
                      <PackageOpen className="h-7 w-7" />
                    </div>
                  )}
                </a>

                {/* 商品详情 */}
                <div className="min-w-0 flex-1">
                  {/* 商品名 — 可点击跳转详情 */}
                  <a href={detailHref} className="text-sm font-semibold text-[#00505a] hover:underline line-clamp-2">
                    {item.product_name ?? "—"}
                  </a>
                  {/* 短描述 */}
                  {item.description && (
                    <p className="mt-0.5 text-xs text-gray-400 line-clamp-1">{item.description}</p>
                  )}
                  {/* 规格 + 修改规格按钮 */}
                  {item.variant_display && (
                    <p className="mt-1 text-xs text-gray-600">
                      <span className="text-gray-400">{t("specs")}:</span> {item.variant_display}
                    </p>
                  )}
                  {!unavailable && item.selected_variants && item.selected_variants.length > 0 && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (expandedItemId === item.item_id) {
                          setExpandedItemId(null);
                        } else {
                          setExpandedItemId(item.item_id);
                          // 懒加载产品属性（只取 selectable 轴）
                          if (!productAttrs[item.product_id]) {
                            getProduct(item.product_id).then((p) => {
                              const selectable: AttrItem[] = [];
                              for (const grp of p.attribute_groups) {
                                for (const attr of grp.items) {
                                  if (attr.selectable) selectable.push(attr);
                                }
                              }
                              setProductAttrs((prev) => ({ ...prev, [item.product_id]: selectable }));
                            }).catch(() => {});
                          }
                          setEditingVariants([...(item.selected_variants || [])]);
                        }
                      }}
                      className="mt-1 inline-flex items-center gap-1 rounded-full border border-[#00505a]/30 px-2.5 py-0.5 text-xs font-medium text-[#00505a] shadow-sm transition-colors hover:bg-[#00505a]/5 active:bg-[#00505a]/10"
                    >
                      {t("editVariant")}
                      {expandedItemId === item.item_id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    </button>
                  )}
                  {/* 标签行：MOQ / 品牌 / 产地 / 交期 / 认证 */}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {item.moq != null && item.moq > 0 && (
                      <span className="inline-flex items-center rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700">
                        MOQ: {item.moq} {item.unit ?? ""}
                      </span>
                    )}
                    {item.brand && (
                      <span className="inline-flex items-center rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700">
                        {item.brand}
                      </span>
                    )}
                    {item.origin && (
                      <span className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                        📍 {item.origin}
                      </span>
                    )}
                    {leadTime && (
                      <span className="inline-flex items-center rounded bg-green-50 px-1.5 py-0.5 text-[11px] text-green-700">
                        🕐 {leadTime}
                      </span>
                    )}
                    {item.certifications.length > 0 && (
                      <span className="inline-flex items-center rounded bg-teal-50 px-1.5 py-0.5 text-[11px] text-teal-700">
                        ✓ {item.certifications.slice(0, 2).join(", ")}
                        {item.certifications.length > 2 ? ` +${item.certifications.length - 2}` : ""}
                      </span>
                    )}
                  </div>
                  {unavailable && item.unavailable_reason && (
                    <span className="mt-1.5 inline-block rounded bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600">
                      {t(`unavailable_${item.unavailable_reason}` as Parameters<typeof t>[0])}
                    </span>
                  )}
                </div>

                {/* 数量 */}
                <div className="w-24 shrink-0 text-center pt-1">
                  {!unavailable ? (
                    <div>
                      <input
                        type="number"
                        key={`qty-${item.item_id}-${item.quantity}`}
                        defaultValue={item.quantity}
                        min={0.01}
                        step="any"
                        onKeyDown={(e) => {
                          if (e.key === "-" || e.key === "e" || e.key === "E") e.preventDefault();
                        }}
                        onBlur={(e) => {
                          const v = parseFloat(e.target.value);
                          if (isNaN(v) || v <= 0) {
                            e.target.value = String(item.quantity);
                            return;
                          }
                          if (v === item.quantity) return;
                          updateCartItem(item.item_id, { quantity: v })
                            .then((cart) => { mutate(cart, false); syncFromCart(cart); })
                            .catch(() => { e.target.value = String(item.quantity); });
                        }}
                        className="h-8 w-20 rounded border border-gray-200 text-center text-sm font-bold text-gray-800 outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
                      />
                      {item.unit && (
                        <span className="block text-[11px] text-gray-400 mt-0.5">{item.unit}</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </div>

                {/* 删除 */}
                <div className="w-10 shrink-0 text-center pt-1">
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(item.item_id)}
                    className="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* 变体编辑面板 */}
              {expandedItemId === item.item_id && (
                <div className="mx-4 mb-2 rounded-lg border border-gray-100 bg-gray-50/50 p-4">
                  {productAttrs[item.product_id] ? (
                    <>
                      {productAttrs[item.product_id].map((attr) => (
                        <div key={attr.key} className="mb-3">
                          <span className="text-xs font-medium text-gray-500 mb-1.5 block">{attr.key}</span>
                          <div className="flex flex-wrap gap-1.5">
                            {attr.values.map((av) => {
                              const isSelected = editingVariants.some(
                                (v) => v.attr_name === attr.key && v.value === av.value
                              );
                              return (
                                <button
                                  key={av.value}
                                  type="button"
                                  onClick={() => {
                                    setEditingVariants((prev) => {
                                      const without = prev.filter((v) => v.attr_name !== attr.key);
                                      if (isSelected) return without;
                                      return [...without, { attr_name: attr.key, value: av.value }];
                                    });
                                  }}
                                  className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                    isSelected
                                      ? "border-[#00505a] bg-[#00505a]/10 text-[#00505a] font-medium"
                                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                  }`}
                                >
                                  {av.value}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                      <div className="mt-3 flex gap-2">
                        <button
                          type="button"
                          disabled={variantSaving}
                          onClick={async () => {
                            setVariantSaving(true);
                            try {
                              const cart = await updateCartItem(item.item_id, { selected_variants: editingVariants });
                              mutate(cart, false);
                              syncFromCart(cart);
                              setExpandedItemId(null);
                            } catch (err: unknown) {
                              if (err instanceof ApiError && err.code === 40520) {
                                toast.error(t("duplicateVariant"));
                              } else {
                                toast.error(err instanceof Error ? err.message : tError("general" as Parameters<typeof tError>[0]));
                              }
                            } finally {
                              setVariantSaving(false);
                            }
                          }}
                          className="rounded-full border border-[#00505a] bg-[#00505a] px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d] active:bg-[#002b2b] disabled:opacity-50"
                        >
                          {t("confirmVariant")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setExpandedItemId(null)}
                          className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 shadow-sm transition-colors hover:bg-gray-50 active:bg-gray-100"
                        >
                          {t("cancelEdit")}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                    </div>
                  )}
                </div>
              )}
              </div>
            );
          })}
        </div>
      </>
      )}
      </div>

      {/* 底部操作栏 — 仅有商品时显示 */}
      {items.length > 0 && (
        <>
          <div className="sticky bottom-0 z-10 flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-3.5 shadow-md">
            {/* 左：全选 + 批量删除 */}
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={handleToggleAll}
                disabled={purchasableItems.length === 0}
                className="h-4 w-4 rounded border-gray-300 text-[#00505a] focus:ring-[#00505a]"
              />
              <span className="text-sm text-gray-700">{tCommon("selectAll")}</span>
            </label>
            {checkedIds.size > 0 && (
              <button
                type="button"
                onClick={() => setBatchDeleteOpen(true)}
                className="inline-flex items-center rounded-full border border-red-200 px-3 py-1 text-xs font-medium text-red-600 shadow-sm transition-colors hover:bg-red-50 active:bg-red-100"
              >
                {t("deleteSelected")}
              </button>
            )}

            {/* 右：统计 + 提交 */}
            <div className="ml-auto flex items-center gap-4">
              <span className="text-sm text-gray-500">
                {t("selected", { count: checkedIds.size })}
                <span className="text-gray-400"> / {items.length}</span>
              </span>
              <button
                type="button"
                disabled={checkedIds.size === 0}
                onClick={handleSubmitInquiry}
                className="inline-flex items-center gap-2 rounded-lg bg-[#e3a615] px-7 py-2.5 text-sm font-bold text-white transition-colors hover:bg-[#c99012] disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed"
              >
                {t("submitInquiry")}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
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
        </>
      )}
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
