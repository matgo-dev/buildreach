"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Loader2,
  MessageSquare,
  Package,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { createRfq } from "@/lib/api/rfqs";
import { operatorProductsApi, type ProductOperatorItem } from "@/lib/api/operatorProducts";
import { getProduct, type AttrItem } from "@/lib/api/products";
import { searchBuyerOrgs, type BuyerOrgBrief } from "@/lib/api/operatorBuyers";
import { useAuthStore } from "@/stores/authStore";

// ---------- 本地行项类型 ----------

interface LocalItem {
  /** 用于去重的 key: product_id + 排序后 variants */
  dedupeKey: string;
  product_id: number;
  product_name: string;
  main_image_url: string;
  category_name: string;
  unit: string;
  moq: number | null;
  selected_variants: Array<{ attr_name: string; value: string }>;
  variant_display: string;
  quantity: number;
  remark: string;
}

function buildDedupeKey(
  productId: number,
  variants: Array<{ attr_name: string; value: string }>,
): string {
  const sorted = [...variants]
    .sort((a, b) => a.attr_name.localeCompare(b.attr_name))
    .map((v) => `${v.attr_name}=${v.value}`)
    .join("|");
  return `${productId}::${sorted}`;
}

function buildVariantDisplay(
  variants: Array<{ attr_name: string; value: string }>,
): string {
  if (variants.length === 0) return "";
  return variants.map((v) => `${v.attr_name}: ${v.value}`).join("; ");
}

// ---------- 草稿持久化类型 ----------

interface OperatorRfqDraft {
  buyerOrg: BuyerOrgBrief | null;
  items: LocalItem[];
  deliveryPlace: string;
  deliveryDate: string;
  targetCurrency: string;
  destinationPort: string;
  preferredTradeTerm: string;
  contactName: string;
  contactPhone: string;
  contactEmail: string;
  remark: string;
}

function emptyDraft(): OperatorRfqDraft {
  return {
    buyerOrg: null,
    items: [],
    deliveryPlace: "",
    deliveryDate: "",
    targetCurrency: "",
    destinationPort: "",
    preferredTradeTerm: "",
    contactName: "",
    contactPhone: "",
    contactEmail: "",
    remark: "",
  };
}

// ---------- 变体轴类型 ----------

type VariantAxis = {
  key: string;
  display: string;
  values: Array<{ value: string; display: string }>;
};

type ProductVariantEntry = {
  variants: VariantAxis[];
  unit: string;
  moq: number | null;
  loading: boolean;
};

// ---------- 添加商品弹窗 ----------

interface AddItemModalProps {
  existingKeys: Set<string>;
  onClose: () => void;
  onAdd: (item: LocalItem) => void;
}

function AddItemModal({ existingKeys, onClose, onAdd }: AddItemModalProps) {
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<ProductOperatorItem[]>([]);
  const [searched, setSearched] = useState(false);

  // 展开状态
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [productVariantMap, setProductVariantMap] = useState<Record<number, ProductVariantEntry>>({});
  const [variantSelection, setVariantSelection] = useState<Record<number, Record<string, string>>>({});
  const [expandedQty, setExpandedQty] = useState("1");
  const [expandedRemark, setExpandedRemark] = useState("");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 防抖搜索商品
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      setSearched(true);
      setExpandedId(null);
      try {
        const res = await operatorProductsApi.list({ keyword: query.trim(), status: "ACTIVE", size: 10 });
        setResults(res.items);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [query]);

  const expandedIdRef = useRef(expandedId);
  expandedIdRef.current = expandedId;
  const variantMapRef = useRef(productVariantMap);
  variantMapRef.current = productVariantMap;

  // 展开/折叠商品变体面板
  const toggleExpand = useCallback(async (productId: number) => {
    if (expandedIdRef.current === productId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(productId);
    setExpandedQty("1");
    setExpandedRemark("");

    if (variantMapRef.current[productId]) return;

    setProductVariantMap((prev) => ({
      ...prev,
      [productId]: { variants: [], unit: "", moq: null, loading: true },
    }));
    try {
      const detail = await getProduct(productId);
      const variants: VariantAxis[] = [];
      for (const group of detail.attribute_groups ?? []) {
        for (const item of group.items ?? []) {
          if (item.selectable && item.values.length > 0) {
            variants.push({
              key: item.key,
              display: item.key,
              values: item.values.map((v) => ({ value: v.value, display: v.value })),
            });
          }
        }
      }
      setProductVariantMap((prev) => ({
        ...prev,
        [productId]: { variants, unit: detail.unit || "PCS", moq: detail.moq, loading: false },
      }));
    } catch {
      setProductVariantMap((prev) => ({
        ...prev,
        [productId]: { variants: [], unit: "PCS", moq: null, loading: false },
      }));
    }
  }, []);

  // 快速添加（无变体商品）
  const handleQuickAdd = useCallback((product: ProductOperatorItem) => {
    const key = buildDedupeKey(product.id, []);
    if (existingKeys.has(key)) {
      toast.error(t("alreadyAdded"));
      return;
    }
    onAdd({
      dedupeKey: key,
      product_id: product.id,
      product_name: product.name,
      main_image_url: product.main_image || "",
      category_name: product.category_name,
      unit: "PCS",
      moq: null,
      selected_variants: [],
      variant_display: "",
      quantity: 1,
      remark: "",
    });
    toast.success(t("quickAdd") + ": " + product.name);
  }, [existingKeys, onAdd, toast, t]);

  // 展开面板内添加（含变体）
  const handleAddWithVariant = useCallback((product: ProductOperatorItem) => {
    const sel = variantSelection[product.id] ?? {};
    const variants = Object.entries(sel)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));

    const qty = Number(expandedQty);
    if (!qty || qty <= 0) {
      toast.error(t("quantity") + " > 0");
      return;
    }

    const key = buildDedupeKey(product.id, variants);
    if (existingKeys.has(key)) {
      toast.error(t("alreadyAdded"));
      return;
    }

    const variantData = productVariantMap[product.id];
    onAdd({
      dedupeKey: key,
      product_id: product.id,
      product_name: product.name,
      main_image_url: product.main_image || "",
      category_name: product.category_name,
      unit: variantData?.unit || "PCS",
      moq: variantData?.moq ?? null,
      selected_variants: variants,
      variant_display: buildVariantDisplay(variants),
      quantity: qty,
      remark: expandedRemark.trim(),
    });
    setExpandedId(null);
  }, [variantSelection, expandedQty, expandedRemark, existingKeys, onAdd, productVariantMap, toast, t]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("addItem")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 搜索框 */}
        <div className="border-b border-gray-100 px-5 py-3">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              autoFocus
              className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            {searching && (
              <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />
            )}
          </div>
        </div>

        {/* 搜索结果列表 */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {searching && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
            </div>
          )}

          {!searching && searched && results.length === 0 && (
            <div className="py-12 text-center text-sm text-gray-400">
              {t("noSearchResult")}
            </div>
          )}

          {!searching && results.length > 0 && (
            <div className="space-y-2">
              {results.map((p) => {
                const isExpanded = expandedId === p.id;
                const variantData = productVariantMap[p.id];
                const hasVariants = variantData && !variantData.loading && variantData.variants.length > 0;
                const noVariantKey = buildDedupeKey(p.id, []);
                const noVariantAdded = existingKeys.has(noVariantKey);

                return (
                  <div key={p.id} className="overflow-hidden rounded-lg border border-gray-200 transition-shadow hover:shadow-sm">
                    {/* 商品信息行 */}
                    <div className="flex gap-3 p-3">
                      {/* 商品图 */}
                      <div className="h-12 w-12 shrink-0 overflow-hidden rounded-md border border-gray-100 bg-gray-50">
                        {p.main_image ? (
                          <img src={p.main_image} alt={p.name} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <Package className="h-5 w-5 text-gray-300" />
                          </div>
                        )}
                      </div>
                      {/* 商品信息 */}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-gray-800">{p.name}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500">
                          <span>{p.spu_code}</span>
                          <span>{p.category_name}</span>
                          {p.origin && <span>{p.origin}</span>}
                          {p.brand && <span>{p.brand}</span>}
                        </div>
                      </div>
                      {/* 操作区 */}
                      <div className="flex shrink-0 flex-col items-end justify-between gap-1">
                        <button
                          type="button"
                          onClick={() => toggleExpand(p.id)}
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50"
                        >
                          {isExpanded ? (
                            <>
                              {t("collapse")}
                              <ChevronDown className="h-3.5 w-3.5" />
                            </>
                          ) : (
                            <>
                              {t("selectVariant")}
                              <ChevronRight className="h-3.5 w-3.5" />
                            </>
                          )}
                        </button>
                        {!isExpanded && (
                          <button
                            type="button"
                            disabled={noVariantAdded}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleQuickAdd(p);
                            }}
                            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                              noVariantAdded
                                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                : "bg-blue-600 text-white hover:bg-blue-700"
                            }`}
                          >
                            {noVariantAdded ? t("alreadyAdded") : t("quickAdd")}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 变体选择器（展开时） */}
                    {isExpanded && (
                      <div className="border-t border-gray-100 bg-gray-50/60 px-4 py-3">
                        {variantData?.loading && (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                          </div>
                        )}
                        {variantData && !variantData.loading && (
                          <>
                            {hasVariants ? (
                              <div className="space-y-3">
                                {variantData.variants.map((axis) => {
                                  const selected = variantSelection[p.id]?.[axis.key];
                                  return (
                                    <div key={axis.key}>
                                      <div className="mb-1.5 text-xs font-medium text-gray-600">{axis.display}</div>
                                      <div className="flex flex-wrap gap-1.5">
                                        {axis.values.map((v) => (
                                          <button
                                            key={v.value}
                                            type="button"
                                            onClick={() => {
                                              setVariantSelection((prev) => ({
                                                ...prev,
                                                [p.id]: {
                                                  ...(prev[p.id] ?? {}),
                                                  [axis.key]: prev[p.id]?.[axis.key] === v.value ? "" : v.value,
                                                },
                                              }));
                                            }}
                                            className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                              selected === v.value
                                                ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                                                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                            }`}
                                          >
                                            {v.display}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <p className="text-xs text-gray-400">{t("noVariants")}</p>
                            )}
                            {/* 数量 + 备注 + 添加 */}
                            <div className="mt-3 space-y-2">
                              <div className="flex items-center gap-3">
                                <label className="text-xs font-medium text-gray-500">{t("quantity")}</label>
                                <input
                                  type="number"
                                  min={0.001}
                                  step="any"
                                  value={expandedQty}
                                  onChange={(e) => setExpandedQty(e.target.value)}
                                  className="h-8 w-24 rounded border border-gray-200 px-2 text-right text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                />
                                <span className="text-xs text-gray-400">{variantData.unit || "PCS"}</span>
                              </div>
                              <div className="flex items-start gap-3">
                                <label className="mt-1 text-xs font-medium text-gray-500">{t("remark")}</label>
                                <textarea
                                  rows={1}
                                  value={expandedRemark}
                                  onChange={(e) => setExpandedRemark(e.target.value)}
                                  className="flex-1 rounded border border-gray-200 px-2 py-1 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                />
                              </div>
                              <div className="flex justify-end">
                                {(() => {
                                  const sel = variantSelection[p.id] ?? {};
                                  const selected_variants = Object.entries(sel)
                                    .filter(([, v]) => v)
                                    .map(([attr_name, value]) => ({ attr_name, value }));
                                  const itemKey = buildDedupeKey(p.id, selected_variants);
                                  const added = existingKeys.has(itemKey);
                                  return (
                                    <button
                                      type="button"
                                      disabled={added}
                                      onClick={() => handleAddWithVariant(p)}
                                      className={`rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                                        added
                                          ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                          : "bg-blue-600 text-white hover:bg-blue-700"
                                      }`}
                                    >
                                      {added ? t("alreadyAdded") : t("addWithVariant")}
                                    </button>
                                  );
                                })()}
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- 主页面内容 ----------

function CreateOnBehalfContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();
  const user = useAuthStore((s) => s.user);

  const draftKey = `op_rfq_draft_${user?.id ?? "anon"}`;

  // ---------- 统一草稿 state ----------

  const [draft, setDraft] = useState<OperatorRfqDraft>(() => {
    if (typeof window === "undefined") return emptyDraft();
    try {
      const saved = sessionStorage.getItem(draftKey);
      if (saved) return JSON.parse(saved);
    } catch {}
    return emptyDraft();
  });

  const updateDraft = useCallback(<K extends keyof OperatorRfqDraft>(
    key: K, value: OperatorRfqDraft[K],
  ) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }, []);

  // 自动持久化
  useEffect(() => {
    try { sessionStorage.setItem(draftKey, JSON.stringify(draft)); } catch {}
  }, [draft, draftKey]);

  // 便捷 getters
  const selectedBuyerOrg = draft.buyerOrg;
  const items = draft.items;

  // ① 买方组织搜索
  const [buyerQuery, setBuyerQuery] = useState("");
  const [buyerSearching, setBuyerSearching] = useState(false);
  const [buyerResults, setBuyerResults] = useState<BuyerOrgBrief[]>([]);
  const [showBuyerDropdown, setShowBuyerDropdown] = useState(false);
  const buyerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const buyerInputRef = useRef<HTMLInputElement>(null);

  // ② 弹窗
  const [addItemOpen, setAddItemOpen] = useState(false);

  // ③ 行内变体编辑
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editVariantMap, setEditVariantMap] = useState<Record<number, ProductVariantEntry>>({});
  const [editVariantSelection, setEditVariantSelection] = useState<Record<string, string>>({});

  // 提交状态
  const [submitting, setSubmitting] = useState(false);

  // 买方组织防抖搜索
  useEffect(() => {
    if (!buyerQuery.trim()) {
      setBuyerResults([]);
      setShowBuyerDropdown(false);
      return;
    }
    if (buyerTimer.current) clearTimeout(buyerTimer.current);
    buyerTimer.current = setTimeout(async () => {
      setBuyerSearching(true);
      try {
        const res = await searchBuyerOrgs(buyerQuery.trim(), 1, 10);
        setBuyerResults(res.items);
        setShowBuyerDropdown(true);
      } catch {
        setBuyerResults([]);
      } finally {
        setBuyerSearching(false);
      }
    }, 300);
    return () => { if (buyerTimer.current) clearTimeout(buyerTimer.current); };
  }, [buyerQuery]);

  const handleSelectBuyerOrg = useCallback((org: BuyerOrgBrief) => {
    updateDraft("buyerOrg", org);
    setBuyerQuery("");
    setShowBuyerDropdown(false);
    setBuyerResults([]);
  }, [updateDraft]);

  const handleClearBuyerOrg = useCallback(() => {
    updateDraft("buyerOrg", null);
    setTimeout(() => buyerInputRef.current?.focus(), 0);
  }, [updateDraft]);

  // 添加行项
  const handleAddItem = useCallback((item: LocalItem) => {
    updateDraft("items", [...draft.items, item]);
  }, [draft.items, updateDraft]);

  // 删除行项
  const handleRemoveItem = useCallback((dedupeKey: string) => {
    updateDraft("items", draft.items.filter((i) => i.dedupeKey !== dedupeKey));
  }, [draft.items, updateDraft]);

  // 行内数量编辑
  const handleQuantityChange = useCallback((dedupeKey: string, qty: number) => {
    if (qty <= 0) return;
    updateDraft("items", draft.items.map((i) =>
      i.dedupeKey === dedupeKey ? { ...i, quantity: qty } : i,
    ));
  }, [draft.items, updateDraft]);

  // 行内变体编辑 - 开始
  const handleStartEditVariant = useCallback(async (idx: number) => {
    const item = draft.items[idx];
    if (!item) return;
    setEditingIdx(idx);

    // 初始化选中状态
    const initial: Record<string, string> = {};
    for (const v of item.selected_variants) {
      initial[v.attr_name] = v.value;
    }
    setEditVariantSelection(initial);

    // 加载变体数据（有缓存则复用）
    if (editVariantMap[item.product_id]) return;
    setEditVariantMap((prev) => ({
      ...prev,
      [item.product_id]: { variants: [], unit: "", moq: null, loading: true },
    }));
    try {
      const detail = await getProduct(item.product_id);
      const variants: VariantAxis[] = [];
      for (const group of detail.attribute_groups ?? []) {
        for (const a of group.items ?? []) {
          if (a.selectable && a.values.length > 0) {
            variants.push({
              key: a.key,
              display: a.key,
              values: a.values.map((v) => ({ value: v.value, display: v.value })),
            });
          }
        }
      }
      setEditVariantMap((prev) => ({
        ...prev,
        [item.product_id]: { variants, unit: detail.unit || "PCS", moq: detail.moq, loading: false },
      }));
    } catch {
      setEditVariantMap((prev) => ({
        ...prev,
        [item.product_id]: { variants: [], unit: "PCS", moq: null, loading: false },
      }));
    }
  }, [draft.items, editVariantMap]);

  // 行内变体编辑 - 确认
  const handleConfirmEditVariant = useCallback(() => {
    if (editingIdx === null) return;
    const item = draft.items[editingIdx];
    if (!item) return;

    const newVariants = Object.entries(editVariantSelection)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));
    const newKey = buildDedupeKey(item.product_id, newVariants);

    // 去重检查（排除自己）
    if (newKey !== item.dedupeKey && new Set(draft.items.map((i) => i.dedupeKey)).has(newKey)) {
      toast.error(t("alreadyAdded"));
      return;
    }

    updateDraft("items", draft.items.map((i, idx) =>
      idx === editingIdx
        ? {
            ...i,
            selected_variants: newVariants,
            variant_display: buildVariantDisplay(newVariants),
            dedupeKey: newKey,
          }
        : i,
    ));
    setEditingIdx(null);
  }, [editingIdx, editVariantSelection, draft.items, updateDraft, toast, t]);

  const existingKeys = useMemo(
    () => new Set(items.map((i) => i.dedupeKey)),
    [items],
  );

  // 表单校验
  const validate = useCallback((): boolean => {
    if (!selectedBuyerOrg) {
      toast.error(t("buyerOrgRequired"));
      return false;
    }
    if (items.length === 0) {
      toast.error(t("itemsRequired"));
      return false;
    }
    return true;
  }, [selectedBuyerOrg, items, toast, t]);

  // 提交（草稿 or 直接提交）
  const handleSubmit = useCallback(async (asDraft: boolean) => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const result = await createRfq({
        buyer_org_id: selectedBuyerOrg!.id,
        as_draft: asDraft,
        items: items.map((item) => ({
          product_id: item.product_id,
          selected_variants: item.selected_variants.length > 0 ? item.selected_variants : undefined,
          quantity: item.quantity,
          remark: item.remark || undefined,
        })),
        requested_delivery_place: draft.deliveryPlace.trim() || undefined,
        destination_port: draft.destinationPort.trim() || undefined,
        preferred_trade_term: draft.preferredTradeTerm.trim() || undefined,
        expected_delivery_date: draft.deliveryDate || undefined,
        target_currency: draft.targetCurrency.trim() || undefined,
        contact_name: draft.contactName.trim() || undefined,
        contact_phone: draft.contactPhone.trim() || undefined,
        contact_email: draft.contactEmail.trim() || undefined,
        remark: draft.remark.trim() || undefined,
      });
      toast.success(asDraft ? t("draftSaved") : t("createSuccess"));
      // 提交成功后清除草稿
      try { sessionStorage.removeItem(draftKey); } catch {}
      router.push(`/${locale}/operator/rfqs/${result.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key as Parameters<typeof tError>[0])); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    validate, selectedBuyerOrg, items, draft, draftKey,
    router, locale, toast, t, tError,
  ]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* 页头 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-xl font-bold text-gray-800">{t("createOnBehalf")}</h1>
      </div>

      {/* ① 买方组织 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("selectBuyerOrg")}</h2>
        {selectedBuyerOrg ? (
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700">
            <span>{selectedBuyerOrg.name}</span>
            {selectedBuyerOrg.code && (
              <span className="text-xs text-blue-400">({selectedBuyerOrg.code})</span>
            )}
            <button
              type="button"
              onClick={handleClearBuyerOrg}
              className="rounded-full p-0.5 text-blue-400 hover:bg-blue-100 hover:text-blue-600 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <div className="relative">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                ref={buyerInputRef}
                type="text"
                value={buyerQuery}
                onChange={(e) => setBuyerQuery(e.target.value)}
                onFocus={() => { if (buyerResults.length > 0) setShowBuyerDropdown(true); }}
                onBlur={() => setTimeout(() => setShowBuyerDropdown(false), 150)}
                placeholder={t("searchBuyerOrg")}
                className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              {buyerSearching && (
                <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />
              )}
            </div>
            {showBuyerDropdown && buyerResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                {buyerResults.map((org) => (
                  <button
                    key={org.id}
                    type="button"
                    onMouseDown={() => handleSelectBuyerOrg(org)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                  >
                    <span className="font-medium text-gray-800">{org.name}</span>
                    {org.code && <span className="text-xs text-gray-400">{org.code}</span>}
                  </button>
                ))}
              </div>
            )}
            {showBuyerDropdown && buyerResults.length === 0 && !buyerSearching && buyerQuery.trim() && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg">
                <p className="px-3 py-2.5 text-sm text-gray-400">{t("noSearchResult")}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ② 商品清单 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
          <button
            type="button"
            onClick={() => setAddItemOpen(true)}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("addItem")}
          </button>
        </div>
        {items.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            {t("itemsRequired")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-3 py-2.5 font-medium">{t("productName")}</th>
                  <th className="w-[140px] px-3 py-2.5 font-medium text-right">{t("quantity")}</th>
                  <th className="w-[40px] px-3 py-2.5 font-medium text-center">{t("remark")}</th>
                  <th className="w-[40px] px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const isEditing = editingIdx === idx;
                  const variantData = editVariantMap[item.product_id];
                  const hasVariants = variantData && !variantData.loading && variantData.variants.length > 0;
                  return (
                    <React.Fragment key={item.dedupeKey}>
                      <tr className="border-t border-gray-100 even:bg-slate-50/50">
                        {/* 商品：图片 + 名称 + 规格 + 编辑变体 */}
                        <td className="px-3 py-2">
                          <div className="flex gap-3">
                            <div className="h-10 w-10 shrink-0 overflow-hidden rounded-md border border-gray-100 bg-gray-50">
                              {item.main_image_url ? (
                                <img src={item.main_image_url} alt="" className="h-full w-full object-cover" />
                              ) : (
                                <div className="flex h-full w-full items-center justify-center">
                                  <Package className="h-4 w-4 text-gray-300" />
                                </div>
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="font-medium text-gray-800 leading-tight">{item.product_name}</div>
                              {item.variant_display && (
                                <div className="text-xs text-gray-500 mt-0.5">{item.variant_display}</div>
                              )}
                              <button
                                type="button"
                                onClick={() => {
                                  if (isEditing) {
                                    setEditingIdx(null);
                                  } else {
                                    handleStartEditVariant(idx);
                                  }
                                }}
                                className="mt-0.5 text-xs text-blue-600 hover:text-blue-700 transition-colors"
                              >
                                {isEditing ? t("collapse") : t("editVariant")}
                              </button>
                            </div>
                          </div>
                        </td>
                        {/* 数量（行内编辑） */}
                        <td className="px-3 py-2 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <input
                              type="number"
                              min={0.001}
                              step="any"
                              value={item.quantity}
                              onChange={(e) => {
                                const v = parseFloat(e.target.value);
                                if (!isNaN(v) && v > 0) handleQuantityChange(item.dedupeKey, v);
                              }}
                              className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                            />
                            <span className="text-xs text-gray-400">{item.unit || "PCS"}</span>
                          </div>
                        </td>
                        {/* 备注 */}
                        <td className="px-3 py-2 text-center">
                          {item.remark ? (
                            <span className="group relative inline-block">
                              <MessageSquare className="h-4 w-4 text-blue-400" />
                              <span className="absolute bottom-full left-1/2 z-50 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white shadow-lg group-hover:block">
                                {item.remark}
                              </span>
                            </span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                        {/* 删除 */}
                        <td className="px-3 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => handleRemoveItem(item.dedupeKey)}
                            className="rounded p-1 text-gray-400 transition-colors hover:text-red-600"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                      {/* 行内变体编辑面板 */}
                      {isEditing && (
                        <tr>
                          <td colSpan={4} className="bg-gray-50/60 px-5 py-3">
                            {variantData?.loading && (
                              <div className="flex items-center justify-center py-3">
                                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                              </div>
                            )}
                            {variantData && !variantData.loading && (
                              <>
                                {hasVariants ? (
                                  <div className="space-y-3">
                                    {variantData.variants.map((axis) => {
                                      const selected = editVariantSelection[axis.key];
                                      return (
                                        <div key={axis.key}>
                                          <div className="mb-1.5 text-xs font-medium text-gray-600">{axis.display}</div>
                                          <div className="flex flex-wrap gap-1.5">
                                            {axis.values.map((v) => (
                                              <button
                                                key={v.value}
                                                type="button"
                                                onClick={() => {
                                                  setEditVariantSelection((prev) => ({
                                                    ...prev,
                                                    [axis.key]: prev[axis.key] === v.value ? "" : v.value,
                                                  }));
                                                }}
                                                className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                                  selected === v.value
                                                    ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                                                    : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                                }`}
                                              >
                                                {v.display}
                                              </button>
                                            ))}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                ) : (
                                  <p className="text-xs text-gray-400">{t("noVariants")}</p>
                                )}
                                <div className="mt-3 flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={handleConfirmEditVariant}
                                    className="rounded-md bg-blue-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
                                  >
                                    {t("confirmVariant")}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setEditingIdx(null)}
                                    className="rounded-md border border-gray-200 px-4 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50"
                                  >
                                    {tCommon("cancel")}
                                  </button>
                                </div>
                              </>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ③ 交货信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">
          {t("section_delivery")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("deliveryPlace")}</label>
            <input
              type="text"
              value={draft.deliveryPlace}
              onChange={(e) => updateDraft("deliveryPlace", e.target.value)}
              placeholder={t("deliveryPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("deliveryDate")}</label>
            <input
              type="date"
              lang={locale}
              value={draft.deliveryDate}
              onChange={(e) => updateDraft("deliveryDate", e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("currency")}</label>
            <select
              value={draft.targetCurrency}
              onChange={(e) => updateDraft("targetCurrency", e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="">—</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
              <option value="TZS">TZS</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("destinationPort")}</label>
            <input
              type="text"
              list="op-destination-port-options"
              value={draft.destinationPort}
              onChange={(e) => updateDraft("destinationPort", e.target.value)}
              placeholder={t("destinationPortPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            <datalist id="op-destination-port-options">
              <option value="Dar es Salaam Port" />
              <option value="Mombasa Port" />
              <option value="Zanzibar Port" />
              <option value="Tanga Port" />
            </datalist>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("preferredTradeTerm")}</label>
            <input
              type="text"
              list="op-trade-term-options"
              value={draft.preferredTradeTerm}
              onChange={(e) => updateDraft("preferredTradeTerm", e.target.value)}
              placeholder={t("preferredTradeTermPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            <datalist id="op-trade-term-options">
              <option value="FOB" />
              <option value="CFR" />
              <option value="CIF" />
              <option value="DAP" />
              <option value="DDP" />
              <option value="EXW" />
            </datalist>
          </div>
        </div>
      </div>

      {/* ④ 联系人 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">
          {t("section_contact")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactName")}</label>
            <input
              type="text"
              value={draft.contactName}
              onChange={(e) => updateDraft("contactName", e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactPhone")}</label>
            <input
              type="text"
              value={draft.contactPhone}
              onChange={(e) => updateDraft("contactPhone", e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactEmail")}</label>
            <input
              type="email"
              value={draft.contactEmail}
              onChange={(e) => updateDraft("contactEmail", e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* ⑤ 备注 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">
          {t("remark")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <textarea
          rows={3}
          value={draft.remark}
          onChange={(e) => updateDraft("remark", e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* 底部操作栏 */}
      <div className="flex justify-end gap-3 pb-8">
        <button
          type="button"
          onClick={() => router.back()}
          disabled={submitting}
          className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
        >
          {tCommon("cancel")}
        </button>
        <button
          type="button"
          onClick={() => handleSubmit(true)}
          disabled={submitting}
          className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("saveDraft")}
        </button>
        <button
          type="button"
          onClick={() => handleSubmit(false)}
          disabled={submitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("submitDirectly")}
        </button>
      </div>

      {/* 添加商品弹窗 */}
      {addItemOpen && (
        <AddItemModal
          existingKeys={existingKeys}
          onClose={() => setAddItemOpen(false)}
          onAdd={handleAddItem}
        />
      )}
    </div>
  );
}

export default function CreateOnBehalfPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_CLAIM]}>
      <CreateOnBehalfContent />
    </RouteGuard>
  );
}
