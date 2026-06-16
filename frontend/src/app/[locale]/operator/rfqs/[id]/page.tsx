"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, Loader2, AlertCircle, Check, Plus, Pencil, Trash2, X } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { usePermissions } from "@/hooks/usePermissions";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import {
  getRfq,
  claimRfq,
  updateRfqItemQty,
  addRfqItem,
  editRfqItem,
  deleteRfqItem,
  type RfqBuyerPublic,
  type RfqItemPublic,
  type RfqOperatorView,
} from "@/lib/api/rfqs";
import {
  listQuotes,
  type RfqQuoteOperatorView,
} from "@/lib/api/quotes";
import { operatorProductsApi, type ProductOperatorItem } from "@/lib/api/operatorProducts";
import { getProduct, type AttrItem } from "@/lib/api/products";
import { formatDate, formatCurrency } from "@/lib/formatters";
import ConfirmModal from "@/components/ui/ConfirmModal";

// ---------- 行内数量编辑组件 ----------

function EditableQuantity({
  item,
  rfqId,
  editable,
  onUpdated,
}: {
  item: RfqItemPublic;
  rfqId: number;
  editable: boolean;
  onUpdated: () => void;
}) {
  const t = useTranslations("rfq");
  const tError = useTranslations("error");
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [qty, setQty] = useState(String(item.quantity));
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    const num = Number(qty);
    if (!num || num <= 0) return;
    if (num === item.quantity) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await updateRfqItemQty(rfqId, item.id, num);
      toast.success(t("quantityUpdated"));
      setEditing(false);
      onUpdated();
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSaving(false);
    }
  }, [rfqId, item.id, item.quantity, qty, toast, t, tError, onUpdated]);

  if (!editable) {
    return (
      <span className="font-semibold text-gray-800">
        {item.quantity} {item.uom_snapshot ?? ""}
      </span>
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => { setQty(String(item.quantity)); setEditing(true); }}
        className="font-semibold text-blue-600 hover:underline"
        title={t("editQuantity")}
      >
        {item.quantity} {item.uom_snapshot ?? ""}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        min={0.001}
        step="any"
        value={qty}
        onChange={(e) => setQty(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setEditing(false); }}
        className="w-20 rounded border border-gray-300 px-2 py-1 text-sm outline-none focus:border-blue-500"
        autoFocus
      />
      <button
        type="button"
        onClick={handleSave}
        disabled={saving}
        className="rounded p-1 text-blue-600 hover:bg-blue-50 disabled:opacity-50"
      >
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

// ---------- 变体选择器（chip 风格） ----------

interface VariantSelectorProps {
  selectableAttrs: AttrItem[];
  selected: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

function VariantSelector({ selectableAttrs, selected, onChange }: VariantSelectorProps) {
  if (selectableAttrs.length === 0) return null;
  return (
    <div className="space-y-3">
      {selectableAttrs.map((attr) => (
        <div key={attr.key}>
          <p className="mb-1.5 text-xs font-medium text-gray-500">{attr.key}</p>
          <div className="flex flex-wrap gap-1.5">
            {attr.values.map((v) => {
              const active = selected[attr.key] === v.value;
              return (
                <button
                  key={v.value}
                  type="button"
                  onClick={() => onChange(attr.key, active ? "" : v.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "border-blue-500 bg-blue-50 text-blue-700"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {v.value}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- 添加行项弹窗 ----------

interface AddItemModalProps {
  rfqId: number;
  onClose: () => void;
  onAdded: () => void;
}

function AddItemModal({ rfqId, onClose, onAdded }: AddItemModalProps) {
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<ProductOperatorItem[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [selectedProduct, setSelectedProduct] = useState<ProductOperatorItem | null>(null);
  const [selectableAttrs, setSelectableAttrs] = useState<AttrItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedVariants, setSelectedVariants] = useState<Record<string, string>>({});
  const [quantity, setQuantity] = useState("1");
  const [remark, setRemark] = useState("");
  const [saving, setSaving] = useState(false);

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 防抖搜索
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await operatorProductsApi.list({ keyword: query.trim(), status: "ACTIVE", size: 10 });
        setResults(res.items);
        setShowDropdown(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [query]);

  // 选中商品后拉详情获取可选属性
  const handleSelectProduct = useCallback(async (product: ProductOperatorItem) => {
    setSelectedProduct(product);
    setShowDropdown(false);
    setQuery(product.name);
    setSelectedVariants({});
    setSelectableAttrs([]);
    setLoadingDetail(true);
    try {
      // 用公开商品详情接口获取 attribute_groups（含 selectable 标记）
      const detail = await getProduct(product.id);
      const selectable: AttrItem[] = [];
      for (const group of detail.attribute_groups) {
        for (const item of group.items) {
          if (item.selectable) selectable.push(item);
        }
      }
      setSelectableAttrs(selectable);
    } catch {
      // 无属性或接口异常，静默处理
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const handleVariantChange = useCallback((key: string, value: string) => {
    setSelectedVariants((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedProduct) return;
    const qty = Number(quantity);
    if (!qty || qty <= 0) {
      toast.error(t("quantityUpdated")); // 复用 quantity 校验
      return;
    }
    setSaving(true);
    try {
      const selected_variants = Object.entries(selectedVariants)
        .filter(([, v]) => v)
        .map(([attr_name, value]) => ({ attr_name, value }));
      await addRfqItem(rfqId, {
        product_id: selectedProduct.id,
        selected_variants: selected_variants.length > 0 ? selected_variants : undefined,
        quantity: qty,
        remark: remark.trim() || undefined,
      });
      toast.success(t("itemAdded"));
      onAdded();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSaving(false);
    }
  }, [rfqId, selectedProduct, selectedVariants, quantity, remark, toast, t, tError, onAdded, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-2xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("addItem")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {/* 商品搜索 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("searchProduct")}</label>
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSelectedProduct(null); }}
                placeholder={t("searchPlaceholder")}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              {searching && (
                <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />
              )}
              {/* 搜索下拉 */}
              {showDropdown && results.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                  {results.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectProduct(p)}
                      className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                    >
                      <div>
                        <p className="font-medium text-gray-800">{p.name}</p>
                        <p className="text-xs text-gray-400">{p.spu_code} · {p.category_name}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {showDropdown && results.length === 0 && !searching && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg">
                  <p className="px-3 py-2.5 text-sm text-gray-400">{t("noSearchResult")}</p>
                </div>
              )}
            </div>
          </div>

          {/* 可选属性（变体选择） */}
          {selectedProduct && (
            <>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                </div>
              ) : (
                selectableAttrs.length > 0 && (
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-500">{t("skuSpec")}</label>
                    <VariantSelector
                      selectableAttrs={selectableAttrs}
                      selected={selectedVariants}
                      onChange={handleVariantChange}
                    />
                  </div>
                )
              )}

              {/* 数量 */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("quantity")}</label>
                <input
                  type="number"
                  min={0.001}
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* 备注 */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("remark")}</label>
                <textarea
                  rows={2}
                  value={remark}
                  onChange={(e) => setRemark(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 border-t border-gray-100 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
          >
            {tCommon("cancel")}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !selectedProduct}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {tCommon("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- 编辑行项弹窗 ----------

interface EditItemModalProps {
  rfqId: number;
  item: RfqItemPublic;
  onClose: () => void;
  onUpdated: () => void;
}

function EditItemModal({ rfqId, item, onClose, onUpdated }: EditItemModalProps) {
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();

  const [selectableAttrs, setSelectableAttrs] = useState<AttrItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(true);

  // 初始化 selected_variants: snapshot → map
  const initVariants: Record<string, string> = {};
  for (const v of item.variant_snapshot ?? []) {
    initVariants[v.attr_name] = v.value;
  }
  const [selectedVariants, setSelectedVariants] = useState<Record<string, string>>(initVariants);
  const [quantity, setQuantity] = useState(String(item.quantity));
  const [remark, setRemark] = useState(item.remark ?? "");
  const [saving, setSaving] = useState(false);

  // 拉商品详情获取可选属性
  useEffect(() => {
    if (!item.product_id) { setLoadingDetail(false); return; }
    getProduct(item.product_id).then((detail) => {
      const selectable: AttrItem[] = [];
      for (const group of detail.attribute_groups) {
        for (const attr of group.items) {
          if (attr.selectable) selectable.push(attr);
        }
      }
      setSelectableAttrs(selectable);
    }).catch(() => {}).finally(() => setLoadingDetail(false));
  }, [item.product_id]);

  const handleVariantChange = useCallback((key: string, value: string) => {
    setSelectedVariants((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    const qty = Number(quantity);
    if (!qty || qty <= 0) return;
    setSaving(true);
    try {
      const selected_variants = Object.entries(selectedVariants)
        .filter(([, v]) => v)
        .map(([attr_name, value]) => ({ attr_name, value }));
      await editRfqItem(rfqId, item.id, {
        selected_variants: selected_variants.length > 0 ? selected_variants : [],
        quantity: qty,
        remark: remark.trim() || undefined,
      });
      toast.success(t("itemUpdated"));
      onUpdated();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSaving(false);
    }
  }, [rfqId, item.id, selectedVariants, quantity, remark, toast, t, tError, onUpdated, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-2xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-gray-800">{t("editItem")}</h3>
            <p className="mt-0.5 text-xs text-gray-400">{item.product_name_snapshot}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {/* 可选属性 */}
          {loadingDetail ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
            </div>
          ) : (
            selectableAttrs.length > 0 && (
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-500">{t("skuSpec")}</label>
                <VariantSelector
                  selectableAttrs={selectableAttrs}
                  selected={selectedVariants}
                  onChange={handleVariantChange}
                />
              </div>
            )
          )}

          {/* 数量 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("quantity")}</label>
            <input
              type="number"
              min={0.001}
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* 备注 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("remark")}</label>
            <textarea
              rows={2}
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 border-t border-gray-100 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
          >
            {tCommon("cancel")}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {tCommon("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- 主页面内容 ----------

function OperatorRfqDetailContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const tQuote = useTranslations("quote");
  const toast = useToast();
  const { hasPermission, user } = usePermissions();
  const rfqId = Number(params.id);

  const { data: rfq, isLoading, error, mutate } = useSWR<RfqBuyerPublic>(
    rfqId ? `operator-rfq-detail-${rfqId}` : null,
    () => getRfq(rfqId),
    { revalidateOnFocus: false },
  );

  // 报价数据（QUOTED 态才请求）— 所有 hooks 必须在早期 return 之前
  const showQuoteReadback = rfq?.status === "QUOTED";
  const { data: quotes } = useSWR<RfqQuoteOperatorView[]>(
    showQuoteReadback ? `operator-rfq-quotes-${rfqId}` : null,
    () => listQuotes(rfqId),
    { revalidateOnFocus: false },
  );
  const activeQuote = quotes?.find((q) => q.quote_status === "ACTIVE") ?? null;

  // 受理
  const [claimOpen, setClaimOpen] = useState(false);
  const [claiming, setClaiming] = useState(false);

  // 行项增删改
  const [addItemOpen, setAddItemOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<RfqItemPublic | null>(null);
  const [deletingItem, setDeletingItem] = useState<RfqItemPublic | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleClaim = useCallback(async () => {
    setClaiming(true);
    try {
      const updated = await claimRfq(rfqId);
      mutate(updated, { revalidate: false });
      setClaimOpen(false);
      toast.success(t("claimSuccess"));
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setClaiming(false);
    }
  }, [rfqId, mutate, toast, t, tError]);

  const handleDeleteItem = useCallback(async () => {
    if (!deletingItem) return;
    setDeleting(true);
    try {
      const updated = await deleteRfqItem(rfqId, deletingItem.id) as unknown as RfqBuyerPublic;
      mutate(updated, { revalidate: false });
      setDeletingItem(null);
      toast.success(t("itemDeleted"));
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setDeleting(false);
    }
  }, [rfqId, deletingItem, mutate, toast, t, tError]);

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error || !rfq) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <AlertCircle className="mb-4 h-12 w-12 text-gray-300" />
        <p className="text-sm text-gray-500">询价单不存在</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          返回
        </button>
      </div>
    );
  }

  const rfqOperator = rfq as unknown as RfqOperatorView;
  const canClaim = rfq.status === "SUBMITTED" && hasPermission("rfq:claim");
  const canBackfillQuote = rfq.status === "PROCESSING" && hasPermission("quote:write");
  // PROCESSING 态且当前用户是受理人时可编辑行项
  const canEditItems =
    rfq.status === "PROCESSING" &&
    rfqOperator.operator_assignee_id != null &&
    rfqOperator.operator_assignee_id === user?.id;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-800">{rfq.rfq_no}</h1>
            <div className="mt-1 flex items-center gap-2">
              <RfqStatusBadge status={rfq.status} />
              {rfq.created_at && (
                <span className="text-xs text-gray-400">
                  {t("submitTime")}: {formatDate(rfq.created_at, locale)}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canClaim && (
            <button
              type="button"
              onClick={() => setClaimOpen(true)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              {t("claim")}
            </button>
          )}
          {canBackfillQuote && (
            <button
              type="button"
              onClick={() => router.push(`/${locale}/operator/rfqs/${rfqId}/quote`)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              {tQuote("backfillTitle")}
            </button>
          )}
        </div>
      </div>

      {/* 商品清单 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
          {canEditItems && (
            <button
              type="button"
              onClick={() => setAddItemOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("addItem")}
            </button>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
                <th className="px-5 py-2.5 font-medium">{t("skuSpec")}</th>
                <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
                {canEditItems && (
                  <th className="px-5 py-2.5 font-medium text-right">{t("actions")}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {rfq.items.map((item) => (
                <tr key={item.id} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name_snapshot ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {item.variant_display ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <EditableQuantity
                      item={item}
                      rfqId={rfqId}
                      editable={canEditItems}
                      onUpdated={() => mutate()}
                    />
                  </td>
                  {canEditItems && (
                    <td className="px-5 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => setEditingItem(item)}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50"
                        >
                          <Pencil className="h-3 w-3" />
                          {t("edit")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeletingItem(item)}
                          disabled={rfq.items.length <= 1}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-red-500 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                          title={rfq.items.length <= 1 ? t("minOneItem") : undefined}
                        >
                          <Trash2 className="h-3 w-3" />
                          {t("deleteItem")}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 交货信息 */}
      {(rfq.requested_delivery_place || rfq.expected_delivery_date || rfq.target_currency) && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("section_delivery")}</h2>
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            {rfq.requested_delivery_place && (
              <div>
                <span className="text-xs text-gray-400">{t("deliveryPlace")}</span>
                <p className="font-medium text-gray-800">{rfq.requested_delivery_place}</p>
              </div>
            )}
            {rfq.expected_delivery_date && (
              <div>
                <span className="text-xs text-gray-400">{t("deliveryDate")}</span>
                <p className="font-medium text-gray-800">
                  {formatDate(rfq.expected_delivery_date, locale, { hour: undefined, minute: undefined })}
                </p>
              </div>
            )}
            {rfq.target_currency && (
              <div>
                <span className="text-xs text-gray-400">{t("currency")}</span>
                <p className="font-medium text-gray-800">{rfq.target_currency}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 联系方式 */}
      {(rfq.contact_name || rfq.contact_phone || rfq.contact_email) && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("section_contact")}</h2>
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            {rfq.contact_name && (
              <div>
                <span className="text-xs text-gray-400">{t("contactName")}</span>
                <p className="font-medium text-gray-800">{rfq.contact_name}</p>
              </div>
            )}
            {rfq.contact_phone && (
              <div>
                <span className="text-xs text-gray-400">{t("contactPhone")}</span>
                <p className="font-medium text-gray-800">{rfq.contact_phone}</p>
              </div>
            )}
            {rfq.contact_email && (
              <div>
                <span className="text-xs text-gray-400">{t("contactEmail")}</span>
                <p className="font-medium text-gray-800">{rfq.contact_email}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 附加要求 */}
      {((rfq.required_certifications && rfq.required_certifications.length > 0) || rfq.remark) && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("section_extra")}</h2>
          {rfq.required_certifications && rfq.required_certifications.length > 0 && (
            <div className="mb-3">
              <span className="text-xs text-gray-400">{t("certifications")}</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {rfq.required_certifications.map((cert) => (
                  <span
                    key={cert}
                    className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700"
                  >
                    {cert}
                  </span>
                ))}
              </div>
            </div>
          )}
          {rfq.remark && (
            <div>
              <span className="text-xs text-gray-400">{t("remark")}</span>
              <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{rfq.remark}</p>
            </div>
          )}
        </div>
      )}

      {/* 报价读回（QUOTED 态） */}
      {showQuoteReadback && activeQuote && (
        <>
          {/* 报价条款 */}
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-gray-700">{tQuote("viewTitle")}</h2>
            <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
              {activeQuote.trade_term && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("tradeTerm")}</span>
                  <p className="font-medium text-gray-800">{tQuote(`tradeTerm_${activeQuote.trade_term}`)}</p>
                </div>
              )}
              {activeQuote.named_place && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("namedPlace")}</span>
                  <p className="font-medium text-gray-800">{activeQuote.named_place}</p>
                </div>
              )}
              {activeQuote.currency && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("currency")}</span>
                  <p className="font-medium text-gray-800">{tQuote(`currency_${activeQuote.currency}`)}</p>
                </div>
              )}
              {activeQuote.valid_until && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("validUntil")}</span>
                  <p className="font-medium text-gray-800">{formatDate(activeQuote.valid_until, locale, { hour: undefined, minute: undefined })}</p>
                </div>
              )}
              {activeQuote.lead_time_days != null && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("leadTimeDays")}</span>
                  <p className="font-medium text-gray-800">{activeQuote.lead_time_days}</p>
                </div>
              )}
              {activeQuote.eta_days != null && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("etaDays")}</span>
                  <p className="font-medium text-gray-800">{activeQuote.eta_days}</p>
                </div>
              )}
              {activeQuote.total_amount != null && (
                <div>
                  <span className="text-xs text-gray-400">{tQuote("totalAmount")}</span>
                  <p className="text-lg font-bold text-gray-800">
                    {formatCurrency(Number(activeQuote.total_amount), activeQuote.currency || "USD", locale)}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* 报价明细 */}
          <div className="rounded-xl border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-gray-700">{tQuote("section_lines")}</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-500">
                    <th className="px-4 py-2.5 font-medium">{tQuote("product")}</th>
                    <th className="px-4 py-2.5 font-medium text-right">{tQuote("unitPrice")}</th>
                    <th className="px-4 py-2.5 font-medium text-right">{tQuote("moq")}</th>
                    <th className="px-4 py-2.5 font-medium text-right">{tQuote("cbm")}</th>
                    <th className="px-4 py-2.5 font-medium text-right">{tQuote("grossWeight")}</th>
                    <th className="px-4 py-2.5 font-medium text-right">{tQuote("tiers")}</th>
                  </tr>
                </thead>
                <tbody>
                  {activeQuote.items.map((qItem) => {
                    // 优先用报价行自带快照，fallback 到询价行
                    const rfqItem = qItem.source_rfq_item_id
                      ? rfq.items.find((ri) => ri.id === qItem.source_rfq_item_id)
                      : undefined;
                    const itemName = qItem.product_name_snapshot ?? rfqItem?.product_name_snapshot ?? "—";
                    const itemVariant = qItem.variant_display ?? rfqItem?.variant_display;
                    return (
                      <tr key={qItem.id} className="border-t border-gray-100 even:bg-slate-50/50">
                        <td className="px-4 py-3 font-medium text-gray-800">
                          {itemName}
                          {itemVariant && (
                            <span className="ml-1 text-xs text-gray-400">{itemVariant}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-800 font-medium">
                          {qItem.unit_price != null ? Number(qItem.unit_price).toFixed(2) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600">
                          {qItem.moq != null ? Number(qItem.moq) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600">
                          {qItem.cbm_per_unit != null ? Number(qItem.cbm_per_unit) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600">
                          {qItem.gross_weight_per_unit != null ? Number(qItem.gross_weight_per_unit) : "—"}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600">
                          {qItem.tiers.length > 0 ? (
                            <div className="text-xs">
                              {[...qItem.tiers].sort((a, b) => a.min_qty - b.min_qty).map((tier, i, sorted) => {
                                const next = sorted[i + 1];
                                const label = next ? `${tier.min_qty}~${next.min_qty - 1}` : `≥${tier.min_qty}`;
                                return <div key={i}>{label}: {Number(tier.unit_price).toFixed(2)}</div>;
                              })}
                            </div>
                          ) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* 受理确认框 */}
      {claimOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-800">{t("claimConfirm")}</h3>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setClaimOpen(false)}
                disabled={claiming}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
              >
                {tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={handleClaim}
                disabled={claiming}
                className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
              >
                {claiming && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {tCommon("confirm")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 添加行项弹窗 */}
      {addItemOpen && (
        <AddItemModal
          rfqId={rfqId}
          onClose={() => setAddItemOpen(false)}
          onAdded={() => mutate()}
        />
      )}

      {/* 编辑行项弹窗 */}
      {editingItem && (
        <EditItemModal
          rfqId={rfqId}
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={() => mutate()}
        />
      )}

      {/* 删除行项确认 */}
      <ConfirmModal
        open={!!deletingItem}
        title={t("deleteItem")}
        description={t("deleteItemConfirm")}
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteItem}
        onCancel={() => setDeletingItem(null)}
      />
    </div>
  );
}

export default function OperatorRfqDetailPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_READ]}>
      <OperatorRfqDetailContent />
    </RouteGuard>
  );
}
