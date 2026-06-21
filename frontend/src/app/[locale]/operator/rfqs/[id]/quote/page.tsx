"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, Loader2, AlertCircle, Plus, Trash2, X, Search } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import { getRfq, type RfqBuyerPublic, type RfqItemPublic } from "@/lib/api/rfqs";
import AttachmentUploader from "@/components/rfq/AttachmentUploader";
import type { AttachmentPublic } from "@/lib/api/attachments";
import { listQuotes } from "@/lib/api/quotes";
import {
  backfillQuote,
  TRADE_TERMS,
  CURRENCIES,
  type QuoteCreatePayload,
  type QuoteLineInput,
  type QuoteTierInput,
  type QuoteHeaderInput,
  type TradeTerm,
  type Currency,
  type LineType,
  type RfqQuoteOperatorView,
} from "@/lib/api/quotes";
import { getProduct, type AttrItem } from "@/lib/api/products";
import { operatorProductsApi, type ProductOperatorItem } from "@/lib/api/operatorProducts";

// ── sessionStorage 草稿 ─────────────────────────────────

function draftKey(rfqId: number) { return `quote-draft-${rfqId}`; }
interface DraftData { header: HeaderState; lines: LineState[]; savedAt: string; }
function saveDraft(rfqId: number, header: HeaderState, lines: LineState[]) {
  try { sessionStorage.setItem(draftKey(rfqId), JSON.stringify({ header, lines, savedAt: new Date().toISOString() })); } catch {}
}
function loadDraft(rfqId: number): DraftData | null {
  try { const r = sessionStorage.getItem(draftKey(rfqId)); return r ? JSON.parse(r) : null; } catch { return null; }
}
function clearDraft(rfqId: number) { try { sessionStorage.removeItem(draftKey(rfqId)); } catch {} }

// ── 阶梯价弹窗 ──────────────────────────────────────────

function QuoteTierModal({ tiers: initial, moq, onConfirm, onCancel, t }: {
  tiers: QuoteTierInput[]; moq: number;
  onConfirm: (tiers: QuoteTierInput[]) => void; onCancel: () => void; t: (k: string) => string;
}) {
  const [tiers, setTiers] = useState<QuoteTierInput[]>(() =>
    initial.length > 0 ? initial.map((tier, i) => (i === 0 ? { ...tier, min_qty: moq || tier.min_qty } : tier)) : [{ min_qty: moq || 1, unit_price: 0 }],
  );
  const update = (idx: number, patch: Partial<QuoteTierInput>) => setTiers((p) => p.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  const addTier = () => { const last = tiers[tiers.length - 1]; setTiers([...tiers, { min_qty: (last?.min_qty ?? 0) + 100, unit_price: 0 }]); };
  const removeTier = (idx: number) => setTiers((p) => p.filter((_, i) => i !== idx));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-base font-semibold text-slate-800">{t("tiers")}</h3>
        <div className="mb-3 space-y-2">
          {tiers.map((tier, idx) => {
            const next = tiers[idx + 1];
            const hint = next && next.min_qty > 0 ? `${tier.min_qty || "?"} ~ ${next.min_qty - 1}` : tier.min_qty > 0 ? `≥ ${tier.min_qty}` : "";
            return (
              <div key={idx} className="rounded-md bg-slate-50 p-3">
                {hint && <div className="mb-1.5 text-[10px] font-medium text-slate-400">{hint}</div>}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label className="text-xs text-slate-500">{t("moq")}</label>
                    <input type="number" min="1" step="any" className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                      value={tier.min_qty || ""} onChange={(e) => update(idx, { min_qty: Number(e.target.value) || 0 })} />
                  </div>
                  <div className="flex-1">
                    <label className="text-xs text-slate-500">{t("unitPrice")}</label>
                    <input type="number" min="0" step="0.01" className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                      value={tier.unit_price || ""} onChange={(e) => update(idx, { unit_price: Number(e.target.value) || 0 })} />
                  </div>
                  <button type="button" onClick={() => removeTier(idx)} className="mb-0.5 text-xs text-red-500 hover:text-red-700" disabled={tiers.length <= 1}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        <button type="button" onClick={addTier} className="mb-4 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800">
          <Plus className="h-3 w-3" /> {t("setTiers")}
        </button>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">{t("cancel")}</button>
          <button type="button" onClick={() => onConfirm(tiers.filter((t) => t.min_qty > 0))} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">{t("tierConfirm")}</button>
        </div>
      </div>
    </div>
  );
}

// ── 变体选择器 ─────────────────────────────────────────

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
                <button key={v.value} type="button"
                  onClick={() => onChange(attr.key, active ? "" : v.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "border-blue-500 bg-blue-50 text-blue-700"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                  }`}>
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

function buildVariantDisplay(variants: Array<{ attr_name: string; value: string }>): string {
  if (variants.length === 0) return "";
  return variants.map((v) => `${v.attr_name}: ${v.value}`).join(", ");
}

// ── 添加商品弹窗 ──────────────────────────────────────

interface AddProductModalProps {
  onClose: () => void;
  onAdd: (item: {
    product_id: number;
    product_name: string;
    selected_variants: Array<{ attr_name: string; value: string }>;
    variant_display: string;
    quantity: string;
    uom: string;
    moq: string;
  }) => void;
}

function AddProductModal({ onClose, onAdd }: AddProductModalProps) {
  const t = useTranslations("quote");
  const tCommon = useTranslations("common");
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<ProductOperatorItem[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [selectedProduct, setSelectedProduct] = useState<ProductOperatorItem | null>(null);
  const [productUnit, setProductUnit] = useState("PCS");
  const [productMoq, setProductMoq] = useState<number | null>(null);
  const [selectableAttrs, setSelectableAttrs] = useState<AttrItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedVariants, setSelectedVariants] = useState<Record<string, string>>({});
  const [quantity, setQuantity] = useState("1");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 防抖搜索商品（operator API，只搜 ACTIVE）
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

  // 选中商品 -> 拉详情获取 selectable 属性 + unit/moq
  const handleSelectProduct = useCallback(async (product: ProductOperatorItem) => {
    setSelectedProduct(product);
    setShowDropdown(false);
    setQuery(product.name);
    setSelectedVariants({});
    setSelectableAttrs([]);
    setProductUnit("PCS");
    setProductMoq(null);
    setLoadingDetail(true);
    try {
      const detail = await getProduct(product.id);
      setProductUnit(detail.unit ?? "PCS");
      setProductMoq(detail.moq ?? null);
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

  const handleConfirm = useCallback(() => {
    if (!selectedProduct) return;
    const qty = Number(quantity);
    if (!qty || qty <= 0) {
      toast.error(t("quantity") + " > 0");
      return;
    }

    const variants = Object.entries(selectedVariants)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));

    onAdd({
      product_id: selectedProduct.id,
      product_name: selectedProduct.name,
      selected_variants: variants,
      variant_display: buildVariantDisplay(variants),
      quantity: String(qty),
      uom: productUnit,
      moq: productMoq ? String(productMoq) : "",
    });
    onClose();
  }, [selectedProduct, selectedVariants, quantity, productUnit, productMoq, onAdd, onClose, toast, t]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="mx-4 w-full max-w-lg rounded-xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        {/* 标题 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("addProductLine")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {/* 商品搜索 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("searchProduct")}</label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input type="text" value={query}
                onChange={(e) => { setQuery(e.target.value); setSelectedProduct(null); }}
                placeholder={t("searchProduct")}
                className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
              {searching && <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />}
              {showDropdown && results.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                  {results.map((p) => (
                    <button key={p.id} type="button" onClick={() => handleSelectProduct(p)}
                      className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50">
                      <div>
                        <p className="font-medium text-gray-800">{p.name}</p>
                        <p className="text-xs text-gray-400">{p.spu_code} &middot; {p.category_name}</p>
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

          {/* 选中商品后：变体 + 数量 */}
          {selectedProduct && (
            <>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                </div>
              ) : (
                selectableAttrs.length > 0 && (
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-500">{t("selectVariant")}</label>
                    <VariantSelector selectableAttrs={selectableAttrs} selected={selectedVariants} onChange={handleVariantChange} />
                  </div>
                )
              )}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("quantity")}</label>
                <input type="number" min={0.001} step="any" value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
              </div>
            </>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 border-t border-gray-100 px-5 py-4">
          <button type="button" onClick={onClose}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50">
            {tCommon("cancel")}
          </button>
          <button type="button" onClick={handleConfirm} disabled={!selectedProduct}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60">
            {tCommon("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 数据类型 ─────────────────────────────────────────────

interface HeaderState {
  trade_term: TradeTerm | ""; named_place: string; currency: Currency;
  valid_until: string; lead_time_days: string; eta_days: string;
}

interface LineState {
  _key: string;
  source_rfq_item_id: number | null;
  line_type: LineType;
  product_id: number | null;
  product_name: string;
  selected_variants: Array<{ attr_name: string; value: string }>;
  variant_display: string;
  quantity: string;
  uom: string;
  unit_price: string;
  moq: string;
  cbm_per_unit: string;
  gross_weight_per_unit: string;
  tiers: QuoteTierInput[];
  remark: string;
}

let _kc = 0;
function nextKey() { return `l-${++_kc}`; }

function buildLinesFromRfqItems(items: RfqItemPublic[]): LineState[] {
  return items.map((item) => ({
    _key: nextKey(),
    source_rfq_item_id: item.id,
    line_type: "PRODUCT" as LineType,
    product_id: item.product_id,
    product_name: item.product_name_snapshot ?? "—",
    selected_variants: item.variant_snapshot ?? [],
    variant_display: item.variant_display ?? "—",
    quantity: String(item.quantity),
    uom: item.uom_snapshot ?? "",
    unit_price: "", moq: "", cbm_per_unit: "", gross_weight_per_unit: "",
    tiers: [], remark: "",
  }));
}

function buildLinesFromQuote(quoteItems: RfqQuoteOperatorView["items"]): LineState[] {
  return quoteItems.map((qi) => ({
    _key: nextKey(),
    source_rfq_item_id: qi.source_rfq_item_id,
    line_type: qi.line_type,
    product_id: qi.product_id,
    product_name: qi.product_name_snapshot ?? "",
    selected_variants: qi.quoted_variants ?? [],
    variant_display: qi.variant_display ?? "",
    quantity: qi.quantity != null ? String(qi.quantity) : "",
    uom: qi.uom ?? "",
    unit_price: qi.unit_price != null ? String(qi.unit_price) : "",
    moq: qi.moq != null ? String(qi.moq) : "",
    cbm_per_unit: qi.cbm_per_unit != null ? String(qi.cbm_per_unit) : "",
    gross_weight_per_unit: qi.gross_weight_per_unit != null ? String(qi.gross_weight_per_unit) : "",
    tiers: qi.tiers?.map((t) => ({ min_qty: t.min_qty, unit_price: t.unit_price })) ?? [],
    remark: qi.remark ?? "",
  }));
}

// ── 主页面 ───────────────────────────────────────────────

function QuoteBackfillContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("quote");
  const tError = useTranslations("error");
  const toast = useToast();
  const rfqId = Number(params.id);

  const { data: rfq, isLoading, error } = useSWR<RfqBuyerPublic>(
    rfqId ? `quote-backfill-rfq-${rfqId}` : null,
    () => getRfq(rfqId), { revalidateOnFocus: false },
  );

  const [header, setHeader] = useState<HeaderState>(
    { trade_term: "", named_place: "", currency: "USD", valid_until: "", lead_time_days: "", eta_days: "" },
  );
  const [lines, setLines] = useState<LineState[]>([]);
  const [linesInited, setLinesInited] = useState(false);
  const [isRequote, setIsRequote] = useState(false);
  const [tierModalIdx, setTierModalIdx] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [quoteAttachments, setQuoteAttachments] = useState<AttachmentPublic[]>([]);

  // 变体编辑
  const [expandedVariantIdx, setExpandedVariantIdx] = useState<number | null>(null);
  const [productAttrsCache, setProductAttrsCache] = useState<Record<number, AttrItem[]>>({});
  const [editingVariants, setEditingVariants] = useState<Array<{ attr_name: string; value: string }>>([]);

  // 初始化
  useEffect(() => {
    if (!rfq || linesInited) return;
    const canQuote = rfq.status === "PROCESSING" || rfq.status === "QUOTED" || rfq.status === "REJECTED";
    if (!canQuote) { setLinesInited(true); return; }

    // 草稿恢复
    const draft = loadDraft(rfqId);
    if (draft) {
      setHeader(draft.header);
      setLines(draft.lines.map((l) => ({ ...l, _key: nextKey() })));
      setLinesInited(true);
      return;
    }

    // QUOTED / REJECTED 都从上一版报价预填
    if (rfq.status === "QUOTED" || rfq.status === "REJECTED") {
      listQuotes(rfqId).then((quotes) => {
        const active = quotes.find((q) => q.quote_status === "ACTIVE");
        if (active) {
          setLines(buildLinesFromQuote(active.items));
          setIsRequote(true);
          setHeader({
            trade_term: (active.trade_term as TradeTerm) || "",
            named_place: active.named_place ?? "",
            currency: (active.currency as Currency) || "USD",
            valid_until: active.valid_until ? active.valid_until.split("T")[0] : "",
            lead_time_days: active.lead_time_days != null ? String(active.lead_time_days) : "",
            eta_days: active.eta_days != null ? String(active.eta_days) : "",
          });
        } else {
          setLines(buildLinesFromRfqItems(rfq.items));
        }
        setLinesInited(true);
      }).catch(() => { setLines(buildLinesFromRfqItems(rfq.items)); setLinesInited(true); });
    } else {
      setLines(buildLinesFromRfqItems(rfq.items));
      setLinesInited(true);
    }
  }, [rfq, rfqId, linesInited]);

  // 自动存草稿
  useEffect(() => {
    if (!linesInited || lines.length === 0) return;
    saveDraft(rfqId, header, lines);
  }, [rfqId, header, lines, linesInited]);

  const updateLine = useCallback((idx: number, patch: Partial<LineState>) => {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }, []);

  const removeLine = useCallback((idx: number) => {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // 通过弹窗添加商品行
  const addProductLine = useCallback((item: {
    product_id: number; product_name: string;
    selected_variants: Array<{ attr_name: string; value: string }>;
    variant_display: string; quantity: string; uom: string; moq: string;
  }) => {
    setLines((prev) => [...prev, {
      _key: nextKey(),
      source_rfq_item_id: null,
      line_type: "PRODUCT" as LineType,
      product_id: item.product_id,
      product_name: item.product_name,
      selected_variants: item.selected_variants,
      variant_display: item.variant_display,
      quantity: item.quantity,
      uom: item.uom,
      unit_price: "",
      moq: item.moq, cbm_per_unit: "", gross_weight_per_unit: "",
      tiers: [], remark: "",
    }]);
  }, []);

  // 直接添加费用行（无需弹窗）
  const addFeeLine = useCallback(() => {
    setLines((prev) => [...prev, {
      _key: nextKey(),
      source_rfq_item_id: null,
      line_type: "FEE" as LineType,
      product_id: null,
      product_name: "",
      selected_variants: [],
      variant_display: "",
      quantity: "1",
      uom: "",
      unit_price: "",
      moq: "", cbm_per_unit: "", gross_weight_per_unit: "",
      tiers: [], remark: "",
    }]);
  }, []);

  // 合计
  const totalAmount = useMemo(() => {
    return lines.reduce((sum, l) => {
      const p = parseFloat(l.unit_price), q = parseFloat(l.quantity);
      return (isNaN(p) || isNaN(q)) ? sum : sum + p * q;
    }, 0);
  }, [lines]);

  // 提交
  const handleSubmit = useCallback(async () => {
    if (lines.length === 0) { toast.error(t("allSkippedError")); return; }

    const hasEmpty = lines.some((l) => l.unit_price === "" || isNaN(parseFloat(l.unit_price)));
    if (hasEmpty) { setShowErrors(true); toast.error(t("unitPriceRequired")); return; }

    if (header.valid_until) {
      if (new Date(header.valid_until).getTime() < Date.now()) { toast.error(t("validUntilPast")); return; }
    }

    setSubmitting(true);
    try {
      const headerPayload: QuoteHeaderInput = {};
      if (header.trade_term) headerPayload.trade_term = header.trade_term as TradeTerm;
      if (header.named_place) headerPayload.named_place = header.named_place;
      if (header.currency) headerPayload.currency = header.currency;
      if (header.valid_until) headerPayload.valid_until = new Date(header.valid_until).toISOString();
      if (header.lead_time_days) headerPayload.lead_time_days = parseInt(header.lead_time_days);
      if (header.eta_days) headerPayload.eta_days = parseInt(header.eta_days);

      const quoteLines: QuoteLineInput[] = lines.map((line) => {
        const out: QuoteLineInput = {
          source_rfq_item_id: line.source_rfq_item_id,
          line_type: line.line_type,
          product_id: line.product_id,
          product_name: line.product_name || undefined,
          selected_variants: line.selected_variants.length > 0 ? line.selected_variants : undefined,
          quantity: parseFloat(line.quantity) || undefined,
          uom: line.uom || undefined,
          unit_price: parseFloat(line.unit_price),
        };
        if (line.moq) out.moq = parseFloat(line.moq);
        if (line.cbm_per_unit) out.cbm_per_unit = parseFloat(line.cbm_per_unit);
        if (line.gross_weight_per_unit) out.gross_weight_per_unit = parseFloat(line.gross_weight_per_unit);
        if (line.tiers.length > 0) out.tiers = line.tiers;
        if (line.remark) out.remark = line.remark;
        return out;
      });

      const payload: QuoteCreatePayload = {
        header: headerPayload,
        lines: quoteLines,
        attachment_ids: quoteAttachments.length > 0 ? quoteAttachments.map((a) => a.id) : undefined,
      };
      await backfillQuote(rfqId, payload);
      clearDraft(rfqId);
      toast.success(t("submitSuccess"));
      router.replace(`/${locale}/operator/rfqs`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally { setSubmitting(false); }
  }, [rfqId, rfq, header, lines, quoteAttachments, router, locale, toast, t, tError]);

  // ── 拦截 / loading ─────────────────────────────────────
  if (rfq && rfq.status !== "PROCESSING" && rfq.status !== "QUOTED" && rfq.status !== "REJECTED") {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <AlertCircle className="mb-4 h-12 w-12 text-amber-400" />
        <p className="text-sm text-gray-600">{t("notProcessing")}</p>
        <button type="button" onClick={() => router.replace(`/${locale}/operator/rfqs`)} className="mt-4 text-sm text-blue-600 hover:underline">{t("backToDetail")}</button>
      </div>
    );
  }
  if (isLoading) return <div className="flex min-h-[400px] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-500" /></div>;
  if (error || !rfq) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <AlertCircle className="mb-4 h-12 w-12 text-gray-300" />
        <button type="button" onClick={() => router.back()} className="mt-4 text-sm text-blue-600 hover:underline">{t("cancel")}</button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24">
      {/* 头部 */}
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => router.back()} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-800">{t("backfillTitle")} &middot; {rfq.rfq_no}</h1>
          <div className="mt-1 flex items-center gap-2">
            <RfqStatusBadge status={rfq.status} />
            {isRequote && <span className="text-xs text-amber-600">{t("requoteHint")}</span>}
          </div>
        </div>
      </div>

      {/* 报价条款 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_terms")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("tradeTerm")}</label>
            <select value={header.trade_term} onChange={(e) => setHeader((h) => ({ ...h, trade_term: e.target.value as TradeTerm | "" }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500">
              <option value="">—</option>
              {TRADE_TERMS.map((c) => <option key={c} value={c}>{t(`tradeTerm_${c}`)}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("namedPlace")}</label>
            <input type="text" value={header.named_place} onChange={(e) => setHeader((h) => ({ ...h, named_place: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("currency")}</label>
            <select value={header.currency} onChange={(e) => setHeader((h) => ({ ...h, currency: e.target.value as Currency }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500">
              {CURRENCIES.map((c) => <option key={c} value={c}>{t(`currency_${c}`)}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("validUntil")}</label>
            <input type="date" lang={locale} value={header.valid_until} onChange={(e) => setHeader((h) => ({ ...h, valid_until: e.target.value }))}
              onClick={(e) => (e.target as HTMLInputElement).showPicker?.()} min={new Date().toISOString().split("T")[0]}
              className="h-9 w-full cursor-pointer rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("leadTimeDays")}</label>
            <input type="number" min="0" value={header.lead_time_days} onChange={(e) => setHeader((h) => ({ ...h, lead_time_days: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("etaDays")}</label>
            <input type="number" min="0" value={header.eta_days} onChange={(e) => setHeader((h) => ({ ...h, eta_days: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500" />
          </div>
        </div>
      </div>

      {/* 区块1：买方需求（只读） */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("rfqReference")}</h2>
        </div>
        {rfq.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-4 py-2.5 font-medium">{t("product")}</th>
                  <th className="px-4 py-2.5 font-medium">{t("spec")}</th>
                  <th className="px-4 py-2.5 font-medium text-right">{t("quantity")}</th>
                </tr>
              </thead>
              <tbody>
                {rfq.items.map((item) => (
                  <tr key={item.id} className="border-t border-gray-100 even:bg-slate-50/50">
                    <td className="px-4 py-2.5 font-medium text-gray-800">{item.product_name_snapshot ?? "—"}</td>
                    <td className="px-4 py-2.5 text-gray-500">{item.variant_display ?? "—"}</td>
                    <td className="px-4 py-2.5 text-right text-gray-700">{item.quantity} {item.uom_snapshot}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-4 text-sm text-gray-400">{t("noItems")}</div>
        )}
        {/* 自由询价：无行项时突出显示需求说明 */}
        {rfq.remark && (
          <div className="border-t border-gray-100 px-5 py-3">
            <span className="text-xs text-gray-400">{t("buyerRemark")}</span>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{rfq.remark}</p>
          </div>
        )}
      </div>

      {/* 区块2：报价明细（可编辑） */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_lines")}</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2.5 font-medium w-[72px]">{t("lineType")}</th>
                <th className="px-3 py-2.5 font-medium">{t("product")}</th>
                <th className="px-3 py-2.5 font-medium text-right w-20">{t("quantity")}</th>
                <th className="px-3 py-2.5 font-medium text-right w-24">{t("unitPrice")} *</th>
                <th className="px-3 py-2.5 font-medium text-right w-20">{t("moq")}</th>
                <th className="px-3 py-2.5 font-medium text-center w-20 whitespace-nowrap">{t("tiers")}</th>
                <th className="px-3 py-2.5 font-medium w-8"></th>
              </tr>
            </thead>
            <tbody>
              {/* 排序：PRODUCT 行在前，FEE 行在后 */}
              {[...lines.map((l, i) => i)]
                .sort((a, b) => {
                  const aFee = lines[a].line_type === "FEE" ? 1 : 0;
                  const bFee = lines[b].line_type === "FEE" ? 1 : 0;
                  return aFee - bFee || a - b;
                })
                .map((idx) => {
                const line = lines[idx];
                const priceEmpty = showErrors && (line.unit_price === "" || isNaN(parseFloat(line.unit_price)));
                const isFee = line.line_type === "FEE";
                const hasProduct = !!line.product_id;
                return (
                  <React.Fragment key={line._key}>
                  <tr className="border-t border-gray-100 even:bg-slate-50/50">
                    {/* 类型 */}
                    <td className="px-3 py-3">
                      <select value={line.line_type}
                        onChange={(e) => {
                          const newType = e.target.value as LineType;
                          updateLine(idx, {
                            line_type: newType,
                            // 切到 FEE 时清空商品关联
                            ...(newType === "FEE" ? { product_id: null, selected_variants: [], variant_display: "", quantity: line.quantity || "1" } : {}),
                          });
                        }}
                        className="h-8 w-full rounded border border-gray-200 px-1 text-xs outline-none focus:border-blue-500">
                        <option value="PRODUCT">{t("lineProduct")}</option>
                        <option value="FEE">{t("lineFee")}</option>
                      </select>
                    </td>
                    {/* 商品/费用名 */}
                    <td className="px-3 py-3">
                      {isFee ? (
                        <input type="text" value={line.product_name} onChange={(e) => updateLine(idx, { product_name: e.target.value })}
                          placeholder={t("feeName")} className="h-8 w-full rounded border border-gray-200 px-2 text-xs outline-none focus:border-blue-500" />
                      ) : hasProduct ? (
                        <div>
                          <div className="flex items-center gap-1">
                            <span className="font-medium text-gray-800 truncate text-xs" title={line.product_name}>{line.product_name}</span>
                          </div>
                          {line.variant_display && line.variant_display !== "—" && (
                            <span className="text-[10px] text-gray-400">{line.variant_display}</span>
                          )}
                          <button type="button"
                            onClick={() => {
                              if (expandedVariantIdx === idx) {
                                setExpandedVariantIdx(null);
                              } else {
                                setExpandedVariantIdx(idx);
                                // 懒加载产品属性（只取 selectable 轴）
                                if (line.product_id && !productAttrsCache[line.product_id]) {
                                  getProduct(line.product_id).then((p) => {
                                    const selectable: AttrItem[] = [];
                                    for (const grp of p.attribute_groups) {
                                      for (const attr of grp.items) {
                                        if (attr.selectable) selectable.push(attr);
                                      }
                                    }
                                    setProductAttrsCache((prev) => ({ ...prev, [line.product_id!]: selectable }));
                                  }).catch(() => {});
                                }
                                setEditingVariants([...line.selected_variants]);
                              }
                            }}
                            className="mt-0.5 block text-[11px] text-blue-600 hover:text-blue-800 hover:underline">
                            {t("editVariant")}
                          </button>
                        </div>
                      ) : (
                        <button type="button" onClick={() => setShowAddModal(true)}
                          className="inline-flex items-center gap-1 rounded-md border border-dashed border-blue-300 px-2.5 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 transition-colors">
                          <Search className="h-3 w-3" /> {t("selectProduct")}
                        </button>
                      )}
                    </td>
                    {/* 数量 */}
                    <td className="px-3 py-3 text-right">
                      <input type="number" min="0" step="any" value={line.quantity}
                        onChange={(e) => updateLine(idx, { quantity: e.target.value })}
                        className="h-8 w-full rounded border border-gray-200 px-2 text-right text-xs outline-none focus:border-blue-500" />
                    </td>
                    {/* 单价 */}
                    <td className="px-3 py-3 text-right">
                      <input type="number" min="0" step="0.01" value={line.unit_price}
                        onChange={(e) => updateLine(idx, { unit_price: e.target.value })}
                        className={`h-8 w-full rounded border px-2 text-right text-xs outline-none focus:border-blue-500 ${priceEmpty ? "border-red-400 bg-red-50" : "border-gray-200"}`}
                        placeholder="0.00" />
                    </td>
                    {/* MOQ — 有阶梯价时锁定为第一档 min_qty */}
                    <td className="px-3 py-3 text-right">
                      {isFee ? <span className="text-xs text-gray-400">—</span> : line.tiers.length > 0 ? (
                        <span className="inline-block h-8 w-full rounded border border-gray-100 bg-gray-50 px-2 text-right text-xs leading-8 text-gray-500" title={t("moqFromTier")}>
                          {line.tiers[0].min_qty || "—"}
                        </span>
                      ) : (
                        <input type="number" min="0" step="any" value={line.moq}
                          onChange={(e) => updateLine(idx, { moq: e.target.value })}
                          className="h-8 w-full rounded border border-gray-200 px-2 text-right text-xs outline-none focus:border-blue-500" />
                      )}
                    </td>
                    {/* 阶梯价 */}
                    <td className="px-3 py-3 text-center">
                      {isFee ? <span className="text-xs text-gray-400">—</span> : (
                        <button type="button" onClick={() => setTierModalIdx(idx)} className="whitespace-nowrap text-xs text-blue-600 hover:underline">
                          {line.tiers.length > 0 ? `${line.tiers.length}` : t("setTiers")}
                        </button>
                      )}
                    </td>
                    {/* 删除 */}
                    <td className="px-3 py-3 text-center">
                      <button type="button" onClick={() => removeLine(idx)} className="text-xs text-red-400 hover:text-red-600">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                  {/* 变体编辑展开行 */}
                  {expandedVariantIdx === idx && line.product_id && (
                    <tr className="border-t border-gray-50 bg-gray-50/50">
                      <td colSpan={7} className="px-4 py-3">
                        {line.product_id && productAttrsCache[line.product_id] ? (
                          productAttrsCache[line.product_id].length > 0 ? (
                            <>
                              {productAttrsCache[line.product_id].map((attr) => (
                                <div key={attr.key} className="mb-2.5">
                                  <span className="text-xs font-medium text-gray-500 mb-1 block">{attr.key}</span>
                                  <div className="flex flex-wrap gap-1.5">
                                    {attr.values.map((av) => {
                                      const isSelected = editingVariants.some(
                                        (v) => v.attr_name === attr.key && v.value === av.value,
                                      );
                                      return (
                                        <button key={av.value} type="button"
                                          onClick={() => {
                                            setEditingVariants((prev) => {
                                              const without = prev.filter((v) => v.attr_name !== attr.key);
                                              if (isSelected) return without;
                                              return [...without, { attr_name: attr.key, value: av.value }];
                                            });
                                          }}
                                          className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                            isSelected
                                              ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                                              : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                          }`}>
                                          {av.value}
                                        </button>
                                      );
                                    })}
                                  </div>
                                </div>
                              ))}
                              <div className="mt-2 flex gap-2">
                                <button type="button"
                                  onClick={() => {
                                    const display = editingVariants.map((v) => `${v.attr_name}: ${v.value}`).join("; ");
                                    updateLine(idx, { selected_variants: [...editingVariants], variant_display: display || "—" });
                                    setExpandedVariantIdx(null);
                                  }}
                                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">
                                  {t("confirmVariant")}
                                </button>
                                <button type="button"
                                  onClick={() => setExpandedVariantIdx(null)}
                                  className="rounded-md border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">
                                  {t("cancel")}
                                </button>
                              </div>
                            </>
                          ) : (
                            <span className="text-xs text-gray-400">{t("noSelectableAttrs")}</span>
                          )
                        ) : (
                          <div className="flex items-center justify-center py-3">
                            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                  </React.Fragment>
                );
              })}
              {/* 末行添加按钮 */}
              <tr className="border-t border-dashed border-gray-200">
                <td colSpan={7} className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <button type="button" onClick={() => setShowAddModal(true)}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-gray-300 py-3 text-sm font-medium text-gray-500 transition-colors hover:border-blue-400 hover:text-blue-600">
                      <Plus className="h-4 w-4" /> {t("addProductLine")}
                    </button>
                    <button type="button" onClick={addFeeLine}
                      className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-2.5 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700">
                      <Plus className="h-3.5 w-3.5" /> {t("addFeeLine")}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 合计 */}
        <div className="border-t border-gray-100 px-5 py-3 text-right">
          <span className="text-sm text-gray-500">{t("totalAmount")}：</span>
          <span className="text-lg font-bold text-gray-800">{header.currency || "USD"} {totalAmount.toFixed(2)}</span>
        </div>
      </div>

      {/* 报价附件 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("quoteAttachments")}</h2>
        <AttachmentUploader
          attachments={quoteAttachments}
          onChange={setQuoteAttachments}
        />
      </div>

      {/* sticky 底栏 */}
      <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-gray-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <button type="button" onClick={() => router.back()}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">{t("cancel")}</button>
          <button type="button" onClick={handleSubmit} disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {t("submit")}
          </button>
        </div>
      </div>

      {/* 弹窗 */}
      {tierModalIdx !== null && (
        <QuoteTierModal tiers={lines[tierModalIdx].tiers} moq={parseFloat(lines[tierModalIdx].moq) || 1}
          onConfirm={(newTiers) => { updateLine(tierModalIdx, { tiers: newTiers, moq: newTiers.length > 0 ? String(newTiers[0].min_qty) : lines[tierModalIdx].moq }); setTierModalIdx(null); }}
          onCancel={() => setTierModalIdx(null)} t={t} />
      )}
      {showAddModal && (
        <AddProductModal
          onClose={() => setShowAddModal(false)}
          onAdd={(item) => { addProductLine(item); setShowAddModal(false); }}
        />
      )}
    </div>
  );
}

export default function QuoteBackfillPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.QUOTE_WRITE]}>
      <QuoteBackfillContent />
    </RouteGuard>
  );
}
