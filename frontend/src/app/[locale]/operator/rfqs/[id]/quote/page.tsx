"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, Loader2, AlertCircle, Plus, Trash2 } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import { getRfq, type RfqBuyerPublic, type RfqItemPublic } from "@/lib/api/rfqs";
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
} from "@/lib/api/quotes";

// ── 阶梯价弹窗（简化版，适配报价场景）──────────────────────

interface TierModalProps {
  tiers: QuoteTierInput[];
  moq: number;
  onConfirm: (tiers: QuoteTierInput[]) => void;
  onCancel: () => void;
  t: (key: string) => string;
}

function QuoteTierModal({ tiers: initial, moq, onConfirm, onCancel, t }: TierModalProps) {
  const [tiers, setTiers] = useState<QuoteTierInput[]>(() =>
    initial.length > 0
      ? initial.map((tier, i) => (i === 0 ? { ...tier, min_qty: moq || tier.min_qty } : tier))
      : [{ min_qty: moq || 1, unit_price: 0 }],
  );

  const update = (idx: number, patch: Partial<QuoteTierInput>) => {
    setTiers((prev) => prev.map((tier, i) => (i === idx ? { ...tier, ...patch } : tier)));
  };

  const addTier = () => {
    const last = tiers[tiers.length - 1];
    setTiers([...tiers, { min_qty: (last?.min_qty ?? 0) + 100, unit_price: 0 }]);
  };

  const removeTier = (idx: number) => {
    setTiers((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-base font-semibold text-slate-800">{t("tiers")}</h3>

        <div className="mb-3 space-y-2">
          {tiers.map((tier, idx) => (
            <div key={idx} className="flex items-end gap-2 rounded-md bg-slate-50 p-3">
              <div className="flex-1">
                <label className="text-xs text-slate-500">{t("moq")}</label>
                <input
                  type="number"
                  min="1"
                  step="any"
                  className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                  value={tier.min_qty || ""}
                  onChange={(e) => update(idx, { min_qty: Number(e.target.value) || 0 })}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-500">{t("unitPrice")}</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                  value={tier.unit_price || ""}
                  onChange={(e) => update(idx, { unit_price: Number(e.target.value) || 0 })}
                />
              </div>
              <button
                type="button"
                onClick={() => removeTier(idx)}
                className="mb-0.5 text-xs text-red-500 hover:text-red-700"
                disabled={tiers.length <= 1}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addTier} className="mb-4 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800">
          <Plus className="h-3 w-3" /> {t("setTiers")}
        </button>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={() => onConfirm(tiers.filter((t) => t.min_qty > 0))}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            {t("tierConfirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 行数据类型 ──────────────────────────────────────────

interface LineState {
  rfq_item_id: number;
  product_name: string;
  variant_display: string;
  quantity: number;
  uom: string;
  skipped: boolean;
  skip_reason: string;
  unit_price: string;
  moq: string;
  cbm_per_unit: string;
  gross_weight_per_unit: string;
  tiers: QuoteTierInput[];
}

function buildInitialLines(items: RfqItemPublic[]): LineState[] {
  return items.map((item) => ({
    rfq_item_id: item.id,
    product_name: item.product_name_snapshot ?? "—",
    variant_display: item.variant_display ?? "\u2014",
    quantity: item.quantity,
    uom: item.uom_snapshot ?? "",
    skipped: false,
    skip_reason: "",
    unit_price: "",
    moq: "",
    cbm_per_unit: "",
    gross_weight_per_unit: "",
    tiers: [],
  }));
}

// ── 主页面内容 ──────────────────────────────────────────

function QuoteBackfillContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("quote");
  const tError = useTranslations("error");
  const toast = useToast();
  const rfqId = Number(params.id);

  // 加载 RFQ 数据
  const { data: rfq, isLoading, error } = useSWR<RfqBuyerPublic>(
    rfqId ? `quote-backfill-rfq-${rfqId}` : null,
    () => getRfq(rfqId),
    { revalidateOnFocus: false },
  );

  // 表头
  const [header, setHeader] = useState<{
    trade_term: TradeTerm | "";
    named_place: string;
    currency: Currency;
    valid_until: string;
    lead_time_days: string;
    eta_days: string;
  }>({
    trade_term: "",
    named_place: "",
    currency: "USD",
    valid_until: "",
    lead_time_days: "",
    eta_days: "",
  });

  // 行数据
  const [lines, setLines] = useState<LineState[]>([]);
  const [linesInited, setLinesInited] = useState(false);

  // RFQ 加载完后初始化行
  if (rfq && !linesInited) {
    setLines(buildInitialLines(rfq.items));
    setLinesInited(true);
  }

  // 阶梯价弹窗
  const [tierModalIdx, setTierModalIdx] = useState<number | null>(null);

  // 提交状态
  const [submitting, setSubmitting] = useState(false);

  // 行内高亮缺 unit_price
  const [showErrors, setShowErrors] = useState(false);

  const updateLine = useCallback((idx: number, patch: Partial<LineState>) => {
    setLines((prev) => prev.map((line, i) => (i === idx ? { ...line, ...patch } : line)));
  }, []);

  // 合计——只算非 skipped 行
  const totalAmount = useMemo(() => {
    return lines.reduce((sum, line) => {
      if (line.skipped) return sum;
      const price = parseFloat(line.unit_price);
      if (isNaN(price)) return sum;
      return sum + price * line.quantity;
    }, 0);
  }, [lines]);

  // 提交
  const handleSubmit = useCallback(async () => {
    // 校验非 skipped 行必须有 unit_price
    const hasEmpty = lines.some((l) => !l.skipped && (l.unit_price === "" || isNaN(parseFloat(l.unit_price))));
    if (hasEmpty) {
      setShowErrors(true);
      toast.error(t("unitPriceRequired"));
      return;
    }

    // 不能全部跳过
    if (lines.every((l) => l.skipped)) {
      toast.error(t("allSkippedError"));
      return;
    }

    // valid_until 不可选过去
    if (header.valid_until) {
      const d = new Date(header.valid_until);
      if (d.getTime() < Date.now()) {
        toast.error(t("validUntilPast"));
        return;
      }
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

      const linePayloads: QuoteLineInput[] = lines.map((line) => {
        if (line.skipped) {
          return {
            rfq_item_id: line.rfq_item_id,
            skipped: true,
            skip_reason: line.skip_reason || undefined,
          };
        }
        const out: QuoteLineInput = {
          rfq_item_id: line.rfq_item_id,
          unit_price: parseFloat(line.unit_price),
        };
        if (line.moq) out.moq = parseFloat(line.moq);
        if (line.cbm_per_unit) out.cbm_per_unit = parseFloat(line.cbm_per_unit);
        if (line.gross_weight_per_unit) out.gross_weight_per_unit = parseFloat(line.gross_weight_per_unit);
        if (line.tiers.length > 0) out.tiers = line.tiers;
        return out;
      });

      const payload: QuoteCreatePayload = { header: headerPayload, lines: linePayloads };
      await backfillQuote(rfqId, payload);
      toast.success(t("submitSuccess"));
      router.replace(`/${locale}/operator/rfqs`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try {
          toast.error(tError(key));
        } catch {
          toast.error(err.message);
        }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }, [rfqId, header, lines, router, locale, toast, t, tError]);

  // ── 非 PROCESSING 态拦截 ──────────────────────────────
  if (rfq && rfq.status !== "PROCESSING") {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <AlertCircle className="mb-4 h-12 w-12 text-amber-400" />
        <p className="text-sm text-gray-600">{t("notProcessing")}</p>
        <button
          type="button"
          onClick={() => router.replace(`/${locale}/operator/rfqs`)}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          {t("backToDetail")}
        </button>
      </div>
    );
  }

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
        <p className="text-sm text-gray-500">—</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          {t("cancel")}
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-24">
      {/* 头部 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-800">
            {t("backfillTitle")} &middot; {rfq.rfq_no}
          </h1>
          <div className="mt-1">
            <RfqStatusBadge status={rfq.status} />
          </div>
        </div>
      </div>

      {/* 区块1 报价条款 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_terms")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* 贸易术语 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("tradeTerm")}</label>
            <select
              value={header.trade_term}
              onChange={(e) => setHeader((h) => ({ ...h, trade_term: e.target.value as TradeTerm | "" }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            >
              <option value="">—</option>
              {TRADE_TERMS.map((code) => (
                <option key={code} value={code}>{t(`tradeTerm_${code}`)}</option>
              ))}
            </select>
          </div>

          {/* 交货地 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("namedPlace")}</label>
            <input
              type="text"
              value={header.named_place}
              onChange={(e) => setHeader((h) => ({ ...h, named_place: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            />
          </div>

          {/* 币种 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("currency")}</label>
            <select
              value={header.currency}
              onChange={(e) => setHeader((h) => ({ ...h, currency: e.target.value as Currency }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            >
              {CURRENCIES.map((code) => (
                <option key={code} value={code}>{t(`currency_${code}`)}</option>
              ))}
            </select>
          </div>

          {/* 有效期 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("validUntil")}</label>
            <input
              type="date"
              value={header.valid_until}
              onChange={(e) => setHeader((h) => ({ ...h, valid_until: e.target.value }))}
              onClick={(e) => (e.target as HTMLInputElement).showPicker?.()}
              min={new Date().toISOString().split("T")[0]}
              className="h-9 w-full cursor-pointer rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            />
          </div>

          {/* 整单工期 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("leadTimeDays")}</label>
            <input
              type="number"
              min="0"
              value={header.lead_time_days}
              onChange={(e) => setHeader((h) => ({ ...h, lead_time_days: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            />
          </div>

          {/* 在途天数 */}
          <div>
            <label className="mb-1 block text-xs text-gray-500">{t("etaDays")}</label>
            <input
              type="number"
              min="0"
              value={header.eta_days}
              onChange={(e) => setHeader((h) => ({ ...h, eta_days: e.target.value }))}
              className="h-9 w-full rounded-md border border-gray-200 px-2 text-sm text-gray-700 outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* 区块2 报价明细 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_lines")}</h2>
          <p className="text-xs text-gray-400">{t("unitPriceHint")}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-4 py-2.5 font-medium">{t("product")}</th>
                <th className="px-4 py-2.5 font-medium">{t("spec")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("quantity")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("unitPrice")} *</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("moq")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("cbm")}</th>
                <th className="px-4 py-2.5 font-medium text-right">{t("grossWeight")}</th>
                <th className="px-4 py-2.5 font-medium text-center">{t("tiers")}</th>
                <th className="px-4 py-2.5 font-medium text-center">{t("skipLabel")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, idx) => {
                const isSkipped = line.skipped;
                const priceEmpty = showErrors && !isSkipped && (line.unit_price === "" || isNaN(parseFloat(line.unit_price)));
                const inputCls = "h-8 w-24 rounded border px-2 text-right text-xs outline-none focus:border-blue-500";
                const disabledCls = "bg-gray-100 text-gray-400 cursor-not-allowed";

                return (
                  <tr key={line.rfq_item_id} className={`border-t border-gray-100 ${isSkipped ? "bg-gray-50/80" : "even:bg-slate-50/50"}`}>
                    <td className={`px-4 py-3 font-medium max-w-[160px] truncate ${isSkipped ? "text-gray-400 line-through" : "text-gray-800"}`} title={line.product_name}>
                      {line.product_name}
                    </td>
                    <td className={`px-4 py-3 max-w-[120px] truncate ${isSkipped ? "text-gray-400" : "text-gray-500"}`} title={line.variant_display}>
                      {line.variant_display}
                    </td>
                    <td className={`px-4 py-3 text-right ${isSkipped ? "text-gray-400" : "text-gray-700"}`}>
                      {line.quantity} {line.uom}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={isSkipped ? "" : line.unit_price}
                        onChange={(e) => updateLine(idx, { unit_price: e.target.value })}
                        disabled={isSkipped}
                        className={`${inputCls} ${isSkipped ? disabledCls : priceEmpty ? "border-red-400 bg-red-50" : "border-gray-200"}`}
                        placeholder={isSkipped ? "—" : "0.00"}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={isSkipped ? "" : line.moq}
                        onChange={(e) => updateLine(idx, { moq: e.target.value })}
                        disabled={isSkipped}
                        className={`h-8 w-20 rounded border px-2 text-right text-xs outline-none focus:border-blue-500 ${isSkipped ? disabledCls : "border-gray-200"}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={isSkipped ? "" : line.cbm_per_unit}
                        onChange={(e) => updateLine(idx, { cbm_per_unit: e.target.value })}
                        disabled={isSkipped}
                        className={`h-8 w-20 rounded border px-2 text-right text-xs outline-none focus:border-blue-500 ${isSkipped ? disabledCls : "border-gray-200"}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={isSkipped ? "" : line.gross_weight_per_unit}
                        onChange={(e) => updateLine(idx, { gross_weight_per_unit: e.target.value })}
                        disabled={isSkipped}
                        className={`h-8 w-20 rounded border px-2 text-right text-xs outline-none focus:border-blue-500 ${isSkipped ? disabledCls : "border-gray-200"}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isSkipped ? (
                        <span className="text-xs text-gray-400">—</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setTierModalIdx(idx)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {line.tiers.length > 0 ? `${line.tiers.length}` : t("setTiers")}
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <label className="relative inline-flex cursor-pointer items-center">
                          <input
                            type="checkbox"
                            checked={isSkipped}
                            onChange={(e) => updateLine(idx, { skipped: e.target.checked })}
                            className="peer sr-only"
                          />
                          <div className="h-5 w-9 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-red-400 peer-checked:after:translate-x-full peer-checked:after:border-white" />
                        </label>
                        {isSkipped && (
                          <input
                            type="text"
                            value={line.skip_reason}
                            onChange={(e) => updateLine(idx, { skip_reason: e.target.value })}
                            placeholder={t("skipReasonPlaceholder")}
                            className="h-6 w-28 rounded border border-gray-200 px-1.5 text-[10px] text-gray-600 outline-none focus:border-blue-500"
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* 合计 */}
        <div className="border-t border-gray-100 px-5 py-3 text-right">
          <span className="text-sm text-gray-500">{t("totalAmount")}：</span>
          <span className="text-lg font-bold text-gray-800">
            {header.currency || "USD"} {totalAmount.toFixed(2)}
          </span>
        </div>
      </div>

      {/* 底部 sticky 提交栏 */}
      <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-gray-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {t("submit")}
          </button>
        </div>
      </div>

      {/* 阶梯价弹窗 */}
      {tierModalIdx !== null && (
        <QuoteTierModal
          tiers={lines[tierModalIdx].tiers}
          moq={parseFloat(lines[tierModalIdx].moq) || 1}
          onConfirm={(newTiers) => {
            updateLine(tierModalIdx, { tiers: newTiers });
            setTierModalIdx(null);
          }}
          onCancel={() => setTierModalIdx(null)}
          t={t}
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
