"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowLeft,
  AlertTriangle,
  Loader2,
  Send,
  Trash2,
  Plus,
  Save,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { getRfq, updateRfq, submitRfq } from "@/lib/api/rfqs";
import ProductSearchModal, {
  makeVariantKey,
  type PickedProduct,
} from "@/components/rfq/ProductSearchModal";
import AttachmentUploader from "@/components/rfq/AttachmentUploader";
import type { AttachmentPublic } from "@/lib/api/attachments";

const CURRENCIES = ["USD", "KES", "CNY"];

interface EditItem {
  product_id: number;
  selected_variants: Array<{ attr_name: string; value: string }>;
  sku_id?: number | null;
  product_name: string;
  variant_display: string;
  unit: string;
  quantity: number;
  product_available: boolean;
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
  const [attachments, setAttachments] = useState<AttachmentPublic[]>([]);

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
            sku_id: undefined,
            product_name: it.product_name_snapshot ?? "\u2014",
            variant_display: it.variant_display ?? "\u2014",
            unit: it.uom_snapshot ?? "PCS",
            quantity: Number(it.quantity),
            product_available: it.product_available !== false,
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
        setAttachments(rfq.attachments ?? []);
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

  const handleAddItem = useCallback((item: PickedProduct) => {
    setItems((prev) => [...prev, { ...item, product_available: true }]);
  }, []);

  // 去重身份 = product_id + 规格指纹(同 SPU 不同规格视作不同行)
  const existingKeys = useMemo(
    () => new Set(items.map((i) => makeVariantKey(i.product_id, i.selected_variants))),
    [items],
  );
  const [showSearch, setShowSearch] = useState(false);

  // 构建请求体（排除失效商品行）
  const availableItems = useMemo(() => items.filter((i) => i.product_available), [items]);
  const buildPayload = useCallback(() => ({
    items: availableItems.map((i) => ({ product_id: i.product_id, selected_variants: i.selected_variants, sku_id: i.sku_id, quantity: i.quantity })),
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
    attachment_ids: attachments.length > 0 ? attachments.map(a => a.id) : undefined,
  }), [availableItems, contactName, contactPhone, contactEmail, deliveryPlace, preferredTradeTerm, destinationPort, deliveryDate, currency, certifications, remark, attachments]);

  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // 自由询价：可用行项 或 remark 至少一个非空
  const hasRemark = !!(remark && remark.trim());
  const canSubmit = availableItems.length > 0 || hasRemark;

  const handleSave = useCallback(async () => {
    if (saving || submitting || !canSubmit) return;
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
  }, [saving, submitting, canSubmit, rfqId, buildPayload, toast, t, tError, router, locale]);

  const handleSubmitDraft = useCallback(async () => {
    if (saving || submitting || !canSubmit) return;
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
    return <div className="flex min-h-[400px] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#0c9468]" /></div>;
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
              {items.map((item, idx) => {
                const unavailable = !item.product_available;
                return (
                <tr key={`${item.product_id}-${idx}`} className={`border-t border-gray-100 ${unavailable ? "bg-gray-50" : "even:bg-slate-50/50"}`}>
                  <td className={`px-5 py-3 font-medium ${unavailable ? "text-gray-400" : "text-gray-800"}`}>
                    <div className="flex items-center gap-1.5">
                      {item.product_name}
                      {unavailable && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-500">
                          <AlertTriangle className="h-3 w-3" />
                          {t("productUnavailable")}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className={`px-5 py-3 text-xs ${unavailable ? "text-gray-300" : "text-gray-500"}`}>
                    {item.variant_display && item.variant_display !== "—"
                      ? item.variant_display
                      : t("noSpec")}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {unavailable ? (
                      <span className="text-sm text-gray-300">{item.quantity} {tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}</span>
                    ) : (
                    <div className="inline-flex items-center gap-1.5">
                      <input type="number" value={item.quantity}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > 0) handleQtyChange(idx, v); }}
                        min={1} className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
                      <span className="text-xs text-gray-500">{tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}</span>
                    </div>
                    )}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button type="button" onClick={() => handleRemoveItem(idx)} className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
                );
              })}
              <tr className="border-t border-gray-100">
                <td colSpan={4} className="px-5 py-3">
                  <button type="button" onClick={() => setShowSearch(true)} className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0c9468] transition-colors hover:text-[#0a7a56]">
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("deliveryDate")}</label>
            <input type="date" lang={locale} value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} min={todayStr}
              onClick={(e) => (e.target as HTMLInputElement).showPicker?.()}
              className="h-10 w-full cursor-pointer rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("currency")}</label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20">
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("destinationPort")}</label>
            <input type="text" list="destination-port-options" value={destinationPort} onChange={(e) => setDestinationPort(e.target.value)}
              placeholder={t("destinationPortPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("contactPhone")}</label>
            <input type="text" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("contactEmail")}</label>
            <input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
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
                <span key={tag} className="inline-flex items-center gap-1 rounded bg-[#0c9468]/10 px-2 py-0.5 text-xs font-medium text-[#0c9468]">
                  {tag}
                  <button type="button" onClick={() => setCertifications((prev) => prev.filter((v) => v !== tag))} className="text-[#0c9468]/50 hover:text-[#0c9468]">x</button>
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
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20" />
          </div>
          <AttachmentUploader
            attachments={attachments}
            onChange={setAttachments}
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pb-8">
        <button type="button" onClick={() => router.back()}
          className="rounded-lg border border-gray-200 px-6 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50">
          {t("cancel")}
        </button>
        <button type="button" disabled={saving || submitting || !canSubmit} onClick={handleSave}
          className={`inline-flex items-center gap-2 rounded-lg border px-6 py-2.5 text-sm font-medium transition-colors ${
            saving || submitting || !canSubmit ? "border-gray-200 text-gray-400 cursor-not-allowed" : "border-[#0c9468] text-[#0c9468] hover:bg-[#0c9468]/5"
          }`}>
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          {!saving && <Save className="h-4 w-4" />}
          {t("saveDraft")}
        </button>
        <button type="button" disabled={submitting || saving || !canSubmit} onClick={handleSubmitDraft}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-colors ${
            submitting || saving || !canSubmit ? "bg-gray-200 text-gray-400 cursor-not-allowed" : "bg-[#0c9468] text-white hover:bg-[#0a7a56]"
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
