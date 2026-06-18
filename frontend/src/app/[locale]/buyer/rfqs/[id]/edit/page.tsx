"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowLeft,
  Loader2,
  Send,
  Trash2,
  Plus,
  Search,
  X,
  ChevronDown,
  ChevronRight,
  Save,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { getRfq, updateRfq, submitRfq } from "@/lib/api/rfqs";
import { listProducts, getProduct, type ProductPublic } from "@/lib/api/products";
import AttachmentUploader from "@/components/rfq/AttachmentUploader";

const CURRENCIES = ["USD", "KES", "CNY"];

interface EditItem {
  product_id: number;
  selected_variants: Array<{ attr_name: string; value: string }>;
  product_name: string;
  variant_display: string;
  unit: string;
  quantity: number;
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
  loading: boolean;
};

// ---------- 商品搜索弹窗（SPU + 变体选择器） ----------

function ProductSearchModal({
  open,
  onClose,
  onAdd,
  existingKeys,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (item: EditItem) => void;
  existingKeys: Set<string>;
}) {
  const t = useTranslations("rfq");
  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<ProductPublic[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [productVariantMap, setProductVariantMap] = useState<Record<number, ProductVariantEntry>>({});
  const [variantSelection, setVariantSelection] = useState<Record<number, Record<string, string>>>({});

  const handleSearch = useCallback(async () => {
    if (!keyword.trim()) return;
    setSearching(true);
    setSearched(true);
    setExpandedId(null);
    try {
      const res = await listProducts({ keyword: keyword.trim(), size: 20 });
      setProducts(res.items);
    } catch {
      setProducts([]);
    } finally {
      setSearching(false);
    }
  }, [keyword]);

  const expandedIdRef = useRef(expandedId);
  expandedIdRef.current = expandedId;
  const variantMapRef = useRef(productVariantMap);
  variantMapRef.current = productVariantMap;

  const toggleExpand = useCallback(async (productId: number) => {
    if (expandedIdRef.current === productId) { setExpandedId(null); return; }
    setExpandedId(productId);
    if (variantMapRef.current[productId]) return;
    setProductVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: true } }));
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
        [productId]: { variants, unit: detail.unit, loading: false },
      }));
    } catch {
      setProductVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: false } }));
    }
  }, []);

  const makeKey = useCallback((productId: number, variants: Array<{ attr_name: string; value: string }>) => {
    const sorted = [...variants].sort((a, b) =>
      a.attr_name.localeCompare(b.attr_name) || a.value.localeCompare(b.value),
    );
    return `${productId}::${JSON.stringify(sorted)}`;
  }, []);

  const handleAddProduct = useCallback((product: ProductPublic, selection: Record<string, string>, unit: string) => {
    const selected_variants = Object.entries(selection)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));
    const variant_display = selected_variants
      .map((v) => `${v.attr_name}: ${v.value}`)
      .join(" / ") || "\u2014";
    onAdd({
      product_id: product.id,
      selected_variants,
      product_name: product.name,
      variant_display,
      unit: unit || product.unit || "PCS",
      quantity: 1,
    });
  }, [onAdd]);

  useEffect(() => {
    if (!open) { setKeyword(""); setProducts([]); setSearched(false); setExpandedId(null); setProductVariantMap({}); setVariantSelection({}); }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("searchProduct")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="border-b border-gray-100 px-5 py-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input type="text" value={keyword} onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleSearch(); } }}
                placeholder={t("searchPlaceholder")} autoFocus
                className="h-10 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
            </div>
            <button type="button" onClick={handleSearch} disabled={searching || !keyword.trim()}
              className="rounded-lg bg-[#00505a] px-4 text-sm font-medium text-white transition-colors hover:bg-[#003f46] disabled:bg-gray-200 disabled:text-gray-400">
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : t("searchProduct")}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {searching && <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-[#00505a]" /></div>}
          {!searching && searched && products.length === 0 && <div className="py-12 text-center text-sm text-gray-400">{t("noSearchResult")}</div>}
          {!searching && products.length > 0 && (
            <div className="space-y-1">
              {products.map((p) => {
                const isExpanded = expandedId === p.id;
                const variantData = productVariantMap[p.id];
                return (
                  <div key={p.id} className="rounded-lg border border-gray-100">
                    <button type="button" onClick={() => toggleExpand(p.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50">
                      {isExpanded ? <ChevronDown className="h-4 w-4 shrink-0 text-gray-400" /> : <ChevronRight className="h-4 w-4 shrink-0 text-gray-400" />}
                      {p.main_image && <img src={p.main_image} alt={p.name} className="h-10 w-10 shrink-0 rounded border border-gray-100 object-cover" />}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-gray-800">{p.name}</div>
                        <div className="text-xs text-gray-400">{p.spu_code}</div>
                      </div>
                    </button>
                    {isExpanded && (
                      <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3 pl-11">
                        {variantData?.loading && <div className="flex items-center justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-gray-400" /></div>}
                        {variantData && !variantData.loading && (
                          <>
                            {variantData.variants.length > 0 && (
                              <div className="space-y-3">
                                {variantData.variants.map((axis) => {
                                  const selected = variantSelection[p.id]?.[axis.key];
                                  return (
                                    <div key={axis.key}>
                                      <div className="mb-1.5 text-xs font-medium text-gray-500">{axis.display}</div>
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
                                                ? "border-[#00505a] bg-[#00505a]/10 text-[#00505a] font-medium"
                                                : "border-gray-200 text-gray-600 hover:border-gray-300"
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
                            )}
                            <div className="mt-3">
                              {(() => {
                                const sel = variantSelection[p.id] ?? {};
                                const selected_variants = Object.entries(sel)
                                  .filter(([, v]) => v)
                                  .map(([attr_name, value]) => ({ attr_name, value }));
                                const itemKey = makeKey(p.id, selected_variants);
                                const added = existingKeys.has(itemKey);
                                return (
                                  <button
                                    type="button"
                                    disabled={added}
                                    onClick={() => handleAddProduct(p, sel, variantData.unit)}
                                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                      added
                                        ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                        : "bg-[#00505a] text-white hover:bg-[#003f46]"
                                    }`}
                                  >
                                    {added ? t("alreadyAdded") : t("add")}
                                  </button>
                                );
                              })()}
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

// ---------- 主内容 ----------

function RfqEditContent() {
  const router = useRouter();
  const locale = useLocale();
  const params = useParams();
  const rfqId = Number(params.id);
  const t = useTranslations("rfq");
  const tMall = useTranslations("mall");
  const tError = useTranslations("error");
  const toast = useToast();

  const [loading, setLoading] = useState(true);
  const [rfqNo, setRfqNo] = useState("");

  // 行项
  const [items, setItems] = useState<EditItem[]>([]);
  // 元数据
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [deliveryPlace, setDeliveryPlace] = useState("");
  const [destinationPort, setDestinationPort] = useState("");
  const [preferredTradeTerm, setPreferredTradeTerm] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [certifications, setCertifications] = useState<string[]>([]);
  const [remark, setRemark] = useState("");
  const [attachmentUrls, setAttachmentUrls] = useState<string[]>([]);

  // 加载已有数据
  useEffect(() => {
    getRfq(rfqId)
      .then((rfq) => {
        if (rfq.status !== "DRAFT") {
          toast.error(t("onlyDraftEditable"));
          router.replace(`/${locale}/buyer/rfqs/${rfqId}`);
          return;
        }
        setRfqNo(rfq.rfq_no);
        setItems(
          rfq.items.map((it) => ({
            product_id: it.product_id,
            selected_variants: it.variant_snapshot ?? [],
            product_name: it.product_name_snapshot ?? "\u2014",
            variant_display: it.variant_display ?? "\u2014",
            unit: it.uom_snapshot ?? "PCS",
            quantity: Number(it.quantity),
          })),
        );
        setContactName(rfq.contact_name ?? "");
        setContactPhone(rfq.contact_phone ?? "");
        setContactEmail(rfq.contact_email ?? "");
        setDeliveryPlace(rfq.requested_delivery_place ?? "");
        setDestinationPort(rfq.destination_port ?? "");
        setPreferredTradeTerm(rfq.preferred_trade_term ?? "");
        setDeliveryDate(rfq.expected_delivery_date ? rfq.expected_delivery_date.slice(0, 10) : "");
        setCurrency(rfq.target_currency ?? "USD");
        setCertifications(rfq.required_certifications ?? []);
        setRemark(rfq.remark ?? "");
        setAttachmentUrls(rfq.attachment_urls ?? []);
      })
      .catch(() => {
        toast.error(t("loadFailed"));
        router.replace(`/${locale}/buyer/rfqs`);
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRemoveItem = useCallback((idx: number) => {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleQtyChange = useCallback((idx: number, qty: number) => {
    if (qty <= 0) return;
    setItems((prev) => prev.map((item, i) => (i === idx ? { ...item, quantity: qty } : item)));
  }, []);

  const handleAddItem = useCallback((item: EditItem) => {
    setItems((prev) => [...prev, item]);
  }, []);

  const makeKey = useCallback((productId: number, variants: Array<{ attr_name: string; value: string }>) => {
    const sorted = [...variants].sort((a, b) =>
      a.attr_name.localeCompare(b.attr_name) || a.value.localeCompare(b.value),
    );
    return `${productId}::${JSON.stringify(sorted)}`;
  }, []);

  const existingKeys = useMemo(() => new Set(items.map((i) => makeKey(i.product_id, i.selected_variants))), [items, makeKey]);
  const [showSearch, setShowSearch] = useState(false);

  // 构建请求体
  const buildPayload = useCallback(() => ({
    items: items.map((i) => ({ product_id: i.product_id, selected_variants: i.selected_variants, quantity: i.quantity })),
    contact_name: contactName || undefined,
    contact_phone: contactPhone || undefined,
    contact_email: contactEmail || undefined,
    requested_delivery_place: deliveryPlace || undefined,
    destination_port: destinationPort || undefined,
    preferred_trade_term: preferredTradeTerm || undefined,
    expected_delivery_date: deliveryDate ? `${deliveryDate}T00:00:00Z` : undefined,
    target_currency: currency || undefined,
    required_certifications: certifications.length > 0 ? certifications : undefined,
    remark: remark || undefined,
    attachment_urls: attachmentUrls.length > 0 ? attachmentUrls : undefined,
  }), [items, contactName, contactPhone, contactEmail, deliveryPlace, destinationPort, preferredTradeTerm, deliveryDate, currency, certifications, remark, attachmentUrls]);

  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSave = useCallback(async () => {
    if (saving || submitting || items.length === 0) return;
    setSaving(true);
    try {
      await updateRfq(rfqId, buildPayload());
      toast.success(t("updateSuccess"));
      router.push(`/${locale}/buyer/rfqs`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key, (err.messageParams ?? {}) as Record<string, string>)); } catch { toast.error(err.message); }
      } else { toast.error(err instanceof Error ? err.message : String(err)); }
    } finally { setSaving(false); }
  }, [saving, submitting, items, rfqId, buildPayload, toast, t, tError, router, locale]);

  const handleSubmitDraft = useCallback(async () => {
    if (saving || submitting || items.length === 0) return;
    setSubmitting(true);
    try {
      // 先保存再提交
      await updateRfq(rfqId, buildPayload());
      await submitRfq(rfqId);
      toast.success(t("submitDraftSuccess"));
      router.push(`/${locale}/buyer/rfqs`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key, (err.messageParams ?? {}) as Record<string, string>)); } catch { toast.error(err.message); }
      } else { toast.error(err instanceof Error ? err.message : String(err)); }
    } finally { setSubmitting(false); }
  }, [saving, submitting, items, rfqId, buildPayload, toast, t, tError, router, locale]);

  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, []);

  // 认证标签输入
  const [certInput, setCertInput] = useState("");

  if (loading) {
    return <div className="flex min-h-[400px] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#00505a]" /></div>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* 页标题 */}
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => router.back()} className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-xl font-bold text-gray-800">{t("editRfq")}</h1>
        <span className="text-sm text-gray-400">{rfqNo}</span>
      </div>

      {/* 商品清单 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
                <th className="px-5 py-2.5 font-medium">{t("skuSpec")}</th>
                <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
                <th className="w-12 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={`${item.product_id}-${idx}`} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">{item.product_name}</td>
                  <td className="px-5 py-3 text-gray-500">{item.variant_display}</td>
                  <td className="px-5 py-3 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <input type="number" value={item.quantity}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > 0) handleQtyChange(idx, v); }}
                        min={1} className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
                      <span className="text-xs text-gray-500">{tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button type="button" onClick={() => handleRemoveItem(idx)} className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={4} className="px-5 py-8 text-center text-sm text-gray-400">{t("noSearchResult")}</td></tr>
              )}
              <tr className="border-t border-gray-100">
                <td colSpan={4} className="px-5 py-3">
                  <button type="button" onClick={() => setShowSearch(true)} className="inline-flex items-center gap-1.5 text-sm font-medium text-[#00505a] transition-colors hover:text-[#003f46]">
                    <Plus className="h-4 w-4" />{t("addProduct")}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 交货信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_delivery")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("deliveryPlace")}</label>
            <input type="text" value={deliveryPlace} onChange={(e) => setDeliveryPlace(e.target.value)} placeholder={t("deliveryPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("deliveryDate")}</label>
            <input type="date" lang={locale} value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} min={todayStr}
              onClick={(e) => (e.target as HTMLInputElement).showPicker?.()}
              className="h-10 w-full cursor-pointer rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("currency")}</label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20">
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("destinationPort")}</label>
            <input type="text" list="destination-port-options" value={destinationPort} onChange={(e) => setDestinationPort(e.target.value)}
              placeholder={t("destinationPortPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
            <datalist id="destination-port-options">
              <option value="Dar es Salaam Port" />
              <option value="Mombasa Port" />
              <option value="Zanzibar Port" />
              <option value="Tanga Port" />
            </datalist>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("preferredTradeTerm")}</label>
            <input type="text" list="trade-term-options" value={preferredTradeTerm} onChange={(e) => setPreferredTradeTerm(e.target.value)}
              placeholder={t("preferredTradeTermPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
            <datalist id="trade-term-options">
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

      {/* 联系方式 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_contact")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("contactName")}</label>
            <input type="text" value={contactName} onChange={(e) => setContactName(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("contactPhone")}</label>
            <input type="text" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("contactEmail")}</label>
            <input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
        </div>
      </div>

      {/* 附加要求 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_extra")}</h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("certifications")}</label>
            <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2">
              {certifications.map((tag) => (
                <span key={tag} className="inline-flex items-center gap-1 rounded bg-[#00505a]/10 px-2 py-0.5 text-xs font-medium text-[#00505a]">
                  {tag}
                  <button type="button" onClick={() => setCertifications((prev) => prev.filter((v) => v !== tag))} className="text-[#00505a]/50 hover:text-[#00505a]">x</button>
                </span>
              ))}
              <input type="text" value={certInput} onChange={(e) => setCertInput(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === ",") && certInput.trim()) {
                    e.preventDefault();
                    const tag = certInput.trim().toUpperCase();
                    if (!certifications.includes(tag)) setCertifications((prev) => [...prev, tag]);
                    setCertInput("");
                  }
                }}
                placeholder="SGS, ISO9001..."
                className="min-w-[120px] flex-1 border-none bg-transparent text-sm outline-none placeholder:text-gray-400" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("remark")}</label>
            <textarea value={remark} onChange={(e) => setRemark(e.target.value)} rows={3}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20" />
          </div>
          <AttachmentUploader
            urls={attachmentUrls}
            onChange={setAttachmentUrls}
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pb-8">
        <button type="button" onClick={() => router.back()}
          className="rounded-lg border border-gray-200 px-6 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50">
          {t("cancel")}
        </button>
        <button type="button" disabled={saving || submitting || items.length === 0} onClick={handleSave}
          className={`inline-flex items-center gap-2 rounded-lg border px-6 py-2.5 text-sm font-medium transition-colors ${
            saving || submitting || items.length === 0 ? "border-gray-200 text-gray-400 cursor-not-allowed" : "border-[#00505a] text-[#00505a] hover:bg-[#00505a]/5"
          }`}>
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          {!saving && <Save className="h-4 w-4" />}
          {t("saveDraft")}
        </button>
        <button type="button" disabled={submitting || saving || items.length === 0} onClick={handleSubmitDraft}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-colors ${
            submitting || saving || items.length === 0 ? "bg-gray-200 text-gray-400 cursor-not-allowed" : "bg-[#00505a] text-white hover:bg-[#003f46]"
          }`}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {t("submitDraft")}
        </button>
      </div>

      <ProductSearchModal open={showSearch} onClose={() => setShowSearch(false)} onAdd={handleAddItem} existingKeys={existingKeys} />
    </div>
  );
}

export default function RfqEditPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_UPDATE]}>
      <RfqEditContent />
    </RouteGuard>
  );
}
