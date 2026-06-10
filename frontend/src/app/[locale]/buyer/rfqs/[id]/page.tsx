"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import { getRfq, cancelRfq, type RfqBuyerPublic } from "@/lib/api/rfqs";
import { formatDate } from "@/lib/formatters";

function RfqDetailContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();
  const rfqId = Number(params.id);

  const { data: rfq, isLoading, error, mutate } = useSWR<RfqBuyerPublic>(
    rfqId ? `rfq-detail-${rfqId}` : null,
    () => getRfq(rfqId),
    { revalidateOnFocus: false },
  );

  // 取消询价
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      const updated = await cancelRfq(rfqId, cancelReason || undefined);
      mutate(updated, { revalidate: false });
      setCancelOpen(false);
      setCancelReason("");
      toast.success(t("cancelSuccess"));
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key)); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setCancelling(false);
    }
  }, [rfqId, cancelReason, mutate, toast, t, tError]);

  // ---- 渲染 ----

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0D4D4D]" />
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
          className="mt-4 text-sm text-[#0D4D4D] hover:underline"
        >
          返回
        </button>
      </div>
    );
  }

  const canCancel = rfq.status === "SUBMITTED";

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
        {canCancel && (
          <button
            type="button"
            onClick={() => setCancelOpen(true)}
            className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
          >
            {t("cancel")}
          </button>
        )}
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
              </tr>
            </thead>
            <tbody>
              {rfq.items.map((item) => (
                <tr key={item.id} className="border-t border-gray-100">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name_snapshot ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {item.sku_spec_snapshot ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-right font-semibold text-gray-800">
                    {item.quantity} {item.uom_snapshot ?? ""}
                  </td>
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
                  {formatDate(rfq.expected_delivery_date, locale, {
                    hour: undefined,
                    minute: undefined,
                  })}
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
                    className="rounded bg-[#0D4D4D]/10 px-2 py-0.5 text-xs font-medium text-[#0D4D4D]"
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

      {/* 取消确认框（含原因输入） */}
      {cancelOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-800">{t("cancelConfirm")}</h3>
            <div className="mt-4">
              <label className="mb-1 block text-sm font-medium text-gray-600">
                {t("cancelReason")}
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
                placeholder={t("cancelReason")}
              />
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => { setCancelOpen(false); setCancelReason(""); }}
                disabled={cancelling}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
              >
                {tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-60"
              >
                {cancelling && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {tCommon("confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function RfqDetailPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_READ]}>
      <RfqDetailContent />
    </RouteGuard>
  );
}
