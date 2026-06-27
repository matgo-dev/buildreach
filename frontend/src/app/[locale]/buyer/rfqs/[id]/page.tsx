"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, Loader2, AlertCircle, AlertTriangle, Ban, CheckCircle2, Pencil, FileText, Package, Download, X } from "lucide-react";
import Link from "next/link";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { usePermissions } from "@/hooks/usePermissions";
import { useToast } from "@/components/ui/Toast";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { ApiError } from "@/lib/api";
import { getRfq, cancelRfq, withdrawRfq, submitRfq, type RfqBuyerPublic, type RfqItemPublic } from "@/lib/api/rfqs";
import { exportQuotePdf } from "@/lib/api/quote-export";
import {
  fetchAttachmentBlob,
  fetchThumbnailBlob,
  downloadAttachment,
  isImageContentType,
  formatFileSize,
  type AttachmentPublic,
} from "@/lib/api/attachments";
import {
  listBuyerQuotes, acceptRfq, rejectRfq,
  type RfqQuoteBuyerPublic, type QuoteItemBuyerPublic,
} from "@/lib/api/quotes";
import { formatDate, formatCurrency } from "@/lib/formatters";
import { imageUrl } from "@/lib/env";

// 需要拉报价的状态集合
const QUOTE_VISIBLE_STATUSES = new Set(["QUOTED", "ACCEPTED", "REJECTED", "EXPIRED"]);

function RfqDetailContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tQ = useTranslations("quote");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();
  const { hasPermission } = usePermissions();
  const rfqId = Number(params.id);

  // RFQ 详情
  const { data: rfq, isLoading, error, mutate } = useSWR<RfqBuyerPublic>(
    rfqId ? `rfq-detail-${rfqId}` : null,
    () => getRfq(rfqId),
    { revalidateOnFocus: false },
  );

  // 报价数据 — SWR key 为 null 时不发请求（满足 hooks 无条件调用规则）
  const quotesSwrKey = rfq && QUOTE_VISIBLE_STATUSES.has(rfq.status)
    ? `rfq-quotes-buyer-${rfqId}`
    : null;
  const { data: quotes, mutate: mutateQuotes } = useSWR(
    quotesSwrKey,
    () => listBuyerQuotes(rfqId),
    { revalidateOnFocus: false },
  );
  const quote = quotes?.[0] ?? null;

  // 有效期过期软提示
  const isExpiredHint = useMemo(() => {
    if (rfq?.status !== "QUOTED" || !quote?.valid_until) return false;
    return new Date(quote.valid_until) < new Date();
  }, [rfq?.status, quote?.valid_until]);

  // 取消询价
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);

  // 撤回改单
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  // 提交草稿
  const [submitOpen, setSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 接受/拒绝
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  // 统一错误展示
  const showError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.messageKey) {
      const key = err.messageKey.replace(/^error\./, "");
      try { toast.error(tError(key)); } catch { toast.error(err.message); }
    } else {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [toast, tError]);

  const handleWithdraw = useCallback(async () => {
    setWithdrawing(true);
    try {
      const updated = await withdrawRfq(rfqId);
      mutate(updated, { revalidate: false });
      setWithdrawOpen(false);
      toast.success(t("withdrawSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setWithdrawing(false);
    }
  }, [rfqId, mutate, toast, t, showError]);

  const handleSubmitDraft = useCallback(async () => {
    setSubmitting(true);
    try {
      const updated = await submitRfq(rfqId);
      mutate(updated, { revalidate: false });
      setSubmitOpen(false);
      toast.success(t("submitDraftSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setSubmitting(false);
    }
  }, [rfqId, mutate, toast, t, showError]);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      const updated = await cancelRfq(rfqId, cancelReason || undefined);
      mutate(updated, { revalidate: false });
      setCancelOpen(false);
      setCancelReason("");
      toast.success(t("cancelSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setCancelling(false);
    }
  }, [rfqId, cancelReason, mutate, toast, t, showError]);

  const handleAccept = useCallback(async () => {
    setAccepting(true);
    try {
      await acceptRfq(rfqId);
      mutate();
      mutateQuotes();
      setAcceptOpen(false);
      toast.success(tQ("acceptSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setAccepting(false);
    }
  }, [rfqId, mutate, mutateQuotes, toast, tQ, showError]);

  const handleReject = useCallback(async () => {
    setRejecting(true);
    try {
      await rejectRfq(rfqId);
      mutate();
      mutateQuotes();
      setRejectOpen(false);
      toast.success(tQ("rejectSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setRejecting(false);
    }
  }, [rfqId, mutate, mutateQuotes, toast, tQ, showError]);

  // ---- 渲染 ----

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#00505a]" />
      </div>
    );
  }

  if (error || !rfq) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <AlertCircle className="mb-4 h-12 w-12 text-gray-300" />
        <p className="text-sm text-gray-500">{tError("rfq.not_found")}</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="mt-4 text-sm text-[#00505a] hover:underline"
        >
          {tCommon("back")}
        </button>
      </div>
    );
  }

  const canEdit = rfq.status === "DRAFT";
  const canSubmitDraft = rfq.status === "DRAFT";
  const canCancel = rfq.status === "SUBMITTED";
  const canWithdraw = rfq.status === "SUBMITTED";
  const canDecide = rfq.status === "QUOTED" && hasPermission(Permissions.RFQ_DECIDE);
  const showQuoteSection = QUOTE_VISIBLE_STATUSES.has(rfq.status);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
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
        <div className="flex items-center gap-2 whitespace-nowrap">
          {canEdit && (
            <button
              type="button"
              onClick={() => router.push(`/${locale}/buyer/rfqs/${rfqId}/edit`)}
              className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-[#00505a]/40 px-4 py-1.5 text-sm font-medium text-[#00505a] shadow-sm transition-colors hover:bg-[#00505a]/5 active:bg-[#00505a]/10"
            >
              <Pencil className="h-3.5 w-3.5" />
              {t("edit")}
            </button>
          )}
          {canSubmitDraft && (
            <button
              type="button"
              onClick={() => setSubmitOpen(true)}
              className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[#00505a] bg-[#00505a] px-4 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d] active:bg-[#002b2b]"
            >
              {t("submitDraft")}
            </button>
          )}
          {canDecide && (
            <>
              <button
                type="button"
                onClick={() => setRejectOpen(true)}
                className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-red-200 px-4 py-1.5 text-sm font-medium text-red-600 shadow-sm transition-colors hover:bg-red-50 active:bg-red-100"
              >
                {tQ("reject")}
              </button>
              <button
                type="button"
                onClick={() => setAcceptOpen(true)}
                className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[#00505a] bg-[#00505a] px-4 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d] active:bg-[#002b2b]"
              >
                {tQ("accept")}
              </button>
            </>
          )}
          {canWithdraw && (
            <button
              type="button"
              onClick={() => setWithdrawOpen(true)}
              className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-amber-200 px-4 py-1.5 text-sm font-medium text-amber-700 shadow-sm transition-colors hover:bg-amber-50 active:bg-amber-100"
            >
              {t("withdraw")}
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              onClick={() => setCancelOpen(true)}
              className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-red-200 px-4 py-1.5 text-sm font-medium text-red-600 shadow-sm transition-colors hover:bg-red-50 active:bg-red-100"
            >
              {t("cancel")}
            </button>
          )}
        </div>
      </div>

      {/* 询价行项 */}
      <RfqItemsCard rfq={rfq} />

      {/* 报价区块（独立卡片） */}
      {showQuoteSection && quote && (
        <QuoteCard rfq={rfq} quote={quote} isExpiredHint={isExpiredHint} locale={locale} onError={showError} />
      )}

      {/* 无报价提示 */}
      {showQuoteSection && !quote && (
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-4">
          <p className="text-sm text-gray-400">{tQ("noQuote")}</p>
        </div>
      )}

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
      {((rfq.required_certifications && rfq.required_certifications.length > 0) || rfq.remark || (rfq.attachments && rfq.attachments.length > 0)) && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("section_extra")}</h2>
          {rfq.required_certifications && rfq.required_certifications.length > 0 && (
            <div className="mb-3">
              <span className="text-xs text-gray-400">{t("certifications")}</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {rfq.required_certifications.map((cert) => (
                  <span
                    key={cert}
                    className="rounded bg-[#00505a]/10 px-2 py-0.5 text-xs font-medium text-[#00505a]"
                  >
                    {cert}
                  </span>
                ))}
              </div>
            </div>
          )}
          {rfq.remark && (
            <div className="mb-3">
              <span className="text-xs text-gray-400">{t("remark")}</span>
              <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{rfq.remark}</p>
            </div>
          )}
          {rfq.attachments && rfq.attachments.length > 0 && (
            <div>
              <span className="text-xs text-gray-400">{t("attachment.label")}</span>
              <AttachmentGallery attachments={rfq.attachments} />
            </div>
          )}
        </div>
      )}

      {/* 报价区块已整合到 ItemsAndQuoteCard */}

      {/* 撤回确认框 */}
      {withdrawOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-800">{t("withdrawConfirm")}</h3>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setWithdrawOpen(false)}
                disabled={withdrawing}
                className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-gray-200 px-4 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50 active:bg-gray-100"
              >
                {tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={handleWithdraw}
                disabled={withdrawing}
                className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-amber-200 bg-amber-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-amber-700 active:bg-amber-800 disabled:opacity-60"
              >
                {withdrawing && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {tCommon("confirm")}
              </button>
            </div>
          </div>
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
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
                placeholder={t("cancelReason")}
              />
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => { setCancelOpen(false); setCancelReason(""); }}
                disabled={cancelling}
                className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-gray-200 px-4 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50 active:bg-gray-100"
              >
                {tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-red-200 bg-red-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-700 active:bg-red-800 disabled:opacity-60"
              >
                {cancelling && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {tCommon("confirm")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 提交草稿确认框 */}
      <ConfirmModal
        open={submitOpen}
        title={t("submitDraft")}
        description={t("submitDraftConfirm")}
        variant="primary"
        loading={submitting}
        confirmLabel={t("submitDraft")}
        onConfirm={handleSubmitDraft}
        onCancel={() => setSubmitOpen(false)}
      />

      {/* 接受确认框 */}
      <ConfirmModal
        open={acceptOpen}
        title={tQ("confirmAcceptTitle")}
        description={tQ("confirmAccept")}
        variant="primary"
        loading={accepting}
        confirmLabel={tQ("accept")}
        onConfirm={handleAccept}
        onCancel={() => setAcceptOpen(false)}
      />

      {/* 拒绝确认框 */}
      <ConfirmModal
        open={rejectOpen}
        title={tQ("confirmRejectTitle")}
        description={tQ("confirmReject")}
        variant="danger"
        loading={rejecting}
        confirmLabel={tQ("reject")}
        onConfirm={handleReject}
        onCancel={() => setRejectOpen(false)}
      />
    </div>
  );
}

// ---- 附件展示 + 灯箱预览 ----

function AttachmentGallery({ attachments }: { attachments: AttachmentPublic[] }) {
  const t = useTranslations("rfq");
  const [thumbUrls, setThumbUrls] = useState<Record<number, string>>({});
  const [thumbFailed, setThumbFailed] = useState<Set<number>>(new Set());
  const [lightboxId, setLightboxId] = useState<number | null>(null);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [lightboxLoading, setLightboxLoading] = useState(false);

  // 加载图片缩略图
  useEffect(() => {
    let cancelled = false;
    for (const att of attachments) {
      if (!isImageContentType(att.content_type)) continue;
      if (thumbUrls[att.id] || thumbFailed.has(att.id)) continue;
      fetchThumbnailBlob(att.id)
        .then((blob) => {
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          setThumbUrls((prev) => ({ ...prev, [att.id]: url }));
        })
        .catch(() => {
          if (!cancelled) setThumbFailed((prev) => new Set(prev).add(att.id));
        });
    }
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachments.map((a) => a.id).join(",")]);

  // 清理缩略图 blob
  useEffect(() => {
    return () => {
      Object.values(thumbUrls).forEach((u) => URL.revokeObjectURL(u));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 打开灯箱
  const openLightbox = useCallback(async (att: AttachmentPublic) => {
    if (!isImageContentType(att.content_type)) {
      // 文档:直接下载
      await downloadAttachment(att.id, att.original_filename);
      return;
    }
    setLightboxId(att.id);
    setLightboxLoading(true);
    try {
      const blob = await fetchAttachmentBlob(att.id);
      const url = URL.createObjectURL(blob);
      setLightboxUrl(url);
    } catch {
      setLightboxId(null);
    } finally {
      setLightboxLoading(false);
    }
  }, []);

  const closeLightbox = useCallback(() => {
    if (lightboxUrl) URL.revokeObjectURL(lightboxUrl);
    setLightboxId(null);
    setLightboxUrl(null);
  }, [lightboxUrl]);

  // Esc 关闭灯箱
  useEffect(() => {
    if (lightboxId === null) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLightbox();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [lightboxId, closeLightbox]);

  const lightboxAtt = attachments.find((a) => a.id === lightboxId);

  return (
    <>
      <div className="mt-2 flex flex-wrap gap-3">
        {attachments.map((att) => (
          <button
            key={att.id}
            type="button"
            onClick={() => openLightbox(att)}
            className="group relative cursor-pointer"
            role="button"
            aria-label={att.original_filename}
          >
            {isImageContentType(att.content_type) && thumbUrls[att.id] ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={thumbUrls[att.id]}
                alt={att.original_filename}
                className="h-20 w-20 rounded-lg border border-gray-200 object-cover transition-shadow hover:shadow-md"
              />
            ) : (
              <div className="flex h-20 w-20 flex-col items-center justify-center rounded-lg border border-gray-200 bg-gray-50 transition-shadow hover:shadow-md">
                {isImageContentType(att.content_type) && !thumbFailed.has(att.id) ? (
                  <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
                ) : (
                  <FileText className="h-6 w-6 text-gray-400" />
                )}
                <span className="mt-1 w-full truncate px-1 text-center text-[10px] text-gray-400">
                  {att.original_filename.length > 12
                    ? att.original_filename.slice(-12)
                    : att.original_filename}
                </span>
                <span className="text-[9px] text-gray-300">
                  {formatFileSize(att.size_bytes)}
                </span>
              </div>
            )}
            {/* 文档下载图标 */}
            {!isImageContentType(att.content_type) && (
              <Download className="absolute bottom-1 right-1 h-3.5 w-3.5 text-gray-400 opacity-0 group-hover:opacity-100" />
            )}
          </button>
        ))}
      </div>

      {/* 灯箱 */}
      {lightboxId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={closeLightbox}
        >
          <div
            className="relative max-h-[90vh] max-w-[90vw] rounded-xl bg-white p-4 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={closeLightbox}
              className="absolute -right-2 -top-2 rounded-full bg-gray-800 p-1 text-white shadow hover:bg-gray-700"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
            {lightboxLoading ? (
              <div className="flex h-64 w-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : lightboxUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={lightboxUrl}
                alt={lightboxAtt?.original_filename ?? ""}
                className="max-h-[80vh] max-w-[80vw] rounded-lg object-contain"
              />
            ) : null}
            {lightboxAtt && (
              <div className="mt-3 flex items-center justify-between text-sm text-gray-500">
                <span className="truncate">{lightboxAtt.original_filename}</span>
                <button
                  type="button"
                  onClick={() => downloadAttachment(lightboxAtt.id, lightboxAtt.original_filename)}
                  className="ml-3 flex items-center gap-1 whitespace-nowrap rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gray-600 shadow-sm hover:bg-gray-50"
                >
                  <Download className="h-3 w-3" />
                  {t("attachment.download")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// ---- 询价行项卡片（独立区块） ----

function RfqItemsCard({ rfq }: { rfq: RfqBuyerPublic }) {
  const t = useTranslations("rfq");

  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 px-5 py-3">
        <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-xs text-gray-500">
              <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
              <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
            </tr>
          </thead>
          <tbody>
            {rfq.items.map((item) => {
              const unavailable = item.product_available === false;
              return (
              <tr key={item.id} className={`border-t border-gray-100 ${unavailable ? "bg-gray-50" : "even:bg-slate-50/50"}`}>
                <td className="px-5 py-3">
                  <div className="flex items-start gap-3">
                    {item.main_image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={imageUrl(item.main_image)}
                        alt=""
                        className={`h-16 w-16 flex-shrink-0 rounded-lg border border-gray-100 object-cover ${unavailable ? "opacity-40 grayscale" : ""}`}
                      />
                    ) : (
                      <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-lg border border-gray-100 bg-gray-50">
                        <Package className={`h-6 w-6 ${unavailable ? "text-gray-200" : "text-gray-300"}`} />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        {unavailable ? (
                          <span className="text-sm font-medium text-gray-400">{item.product_name_snapshot ?? "—"}</span>
                        ) : (
                          <Link
                            href={`/mall/products/${item.product_id}`}
                            className="text-sm font-medium text-gray-800 hover:text-[#00505a] hover:underline"
                          >
                            {item.product_name_snapshot ?? "—"}
                          </Link>
                        )}
                        {unavailable && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-500">
                            <Ban className="h-3 w-3" />
                            {t("productUnavailable")}
                          </span>
                        )}
                      </div>
                      {(item.spu_code || item.brand || item.origin) && (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {item.spu_code && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                              SPU: {item.spu_code}
                            </span>
                          )}
                          {item.brand && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                              {item.brand}
                            </span>
                          )}
                          {item.origin && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                              {item.origin}
                            </span>
                          )}
                        </div>
                      )}
                      {item.category_name && (
                        <p className="mt-0.5 text-[10px] text-gray-400">{item.category_name}</p>
                      )}

                    </div>
                  </div>
                </td>
                <td className={`px-5 py-3 text-right align-top font-semibold ${unavailable ? "text-gray-400" : "text-gray-800"}`}>
                  {item.quantity} {item.uom_snapshot ?? ""}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- 报价卡片（独立区块） ----

// 允许导出报价单的 RFQ 状态
const EXPORTABLE_STATUSES = new Set(["QUOTED", "ACCEPTED"]);

function QuoteCard({
  rfq,
  quote,
  isExpiredHint,
  locale,
  onError,
}: {
  rfq: RfqBuyerPublic;
  quote: RfqQuoteBuyerPublic;
  isExpiredHint: boolean;
  locale: string;
  onError: (err: unknown) => void;
}) {
  const tQ = useTranslations("quote");
  const currency = quote.currency ?? "USD";
  const isAccepted = rfq.status === "ACCEPTED";
  const canExport = EXPORTABLE_STATUSES.has(rfq.status);
  const [downloading, setDownloading] = useState(false);

  const toast = useToast();
  const handleDownload = async () => {
    setDownloading(true);
    try {
      const result = await exportQuotePdf(rfq.id);
      if (result.status === "generating") {
        toast.warning(tQ("documentGeneratingToast"));
      } else if (result.status === "failed") {
        toast.error(tQ("documentFailedToast"));
      }
    } catch (err: unknown) {
      onError(err);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      {/* 标题 */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-700">{tQ("viewTitle")}</h2>
          {isAccepted && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
              <CheckCircle2 className="h-3 w-3" />
              {tQ("acceptedTag")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{quote.quote_no}</span>
          {canExport && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[#00505a]/40 px-3 py-1 text-xs font-medium text-[#00505a] shadow-sm transition-colors hover:bg-[#00505a]/5 active:bg-[#00505a]/10 disabled:opacity-50"
            >
              {downloading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              {tQ("downloadPdf")}
            </button>
          )}
        </div>
      </div>

      {/* 过期软提示 */}
      {isExpiredHint && (
        <div className="mx-5 mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          {tQ("expiredHint")}
        </div>
      )}

      {/* 报价条款 */}
      <div className="grid grid-cols-2 gap-3 border-b border-gray-100 px-5 py-4 text-sm sm:grid-cols-4">
        {quote.trade_term && (
          <div>
            <span className="text-xs text-gray-400">{tQ("tradeTerm")}</span>
            <p className="font-medium text-gray-800">{quote.trade_term}</p>
          </div>
        )}
        {quote.named_place && (
          <div>
            <span className="text-xs text-gray-400">{tQ("namedPlace")}</span>
            <p className="font-medium text-gray-800">{quote.named_place}</p>
          </div>
        )}
        {quote.currency && (
          <div>
            <span className="text-xs text-gray-400">{tQ("currency")}</span>
            <p className="font-medium text-gray-800">{quote.currency}</p>
          </div>
        )}
        {quote.valid_until && (
          <div>
            <span className="text-xs text-gray-400">{tQ("validUntil")}</span>
            <p className="font-medium text-gray-800">
              {formatDate(quote.valid_until, locale, { hour: undefined, minute: undefined })}
            </p>
          </div>
        )}
        {quote.lead_time_days != null && (
          <div>
            <span className="text-xs text-gray-400">{tQ("leadTimeDays")}</span>
            <p className="font-medium text-gray-800">{quote.lead_time_days}</p>
          </div>
        )}
        {quote.eta_days != null && (
          <div>
            <span className="text-xs text-gray-400">{tQ("etaDays")}</span>
            <p className="font-medium text-gray-800">{quote.eta_days}</p>
          </div>
        )}
        {quote.total_amount != null && (
          <div>
            <span className="text-xs text-gray-400">{tQ("totalAmount")}</span>
            <p className="text-base font-bold text-[#00505a]">
              {formatCurrency(Number(quote.total_amount), currency, locale)}
            </p>
          </div>
        )}
      </div>

      {/* 报价明细表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-xs text-gray-500 whitespace-nowrap">
              <th className="px-4 py-2.5 font-medium">{tQ("product")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("quantity")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("unitPrice")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("moq")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("cbm")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("grossWeight")}</th>
              <th className="px-4 py-2.5 font-medium text-right">{tQ("totalAmount")}</th>
            </tr>
          </thead>
          <tbody>
            {quote.items.map((qi) => (
              <QuoteLineRow key={qi.id} qi={qi} currency={currency} locale={locale} />
            ))}
          </tbody>
        </table>
      </div>

      {/* 报价附件（买方可见） */}
      {quote.attachments && quote.attachments.length > 0 && (
        <div className="border-t border-gray-100 px-5 py-4">
          <h3 className="mb-3 text-sm font-medium text-gray-700">{tQ("quoteAttachments")}</h3>
          <AttachmentGallery attachments={quote.attachments} />
        </div>
      )}
    </div>
  );
}

// ---- 报价行子组件 ----

function QuoteLineRow({
  qi,
  currency,
  locale,
}: {
  qi: QuoteItemBuyerPublic;
  currency: string;
  locale: string;
}) {
  const tQ = useTranslations("quote");
  const [showTiers, setShowTiers] = useState(false);

  const isFee = qi.line_type === "FEE";
  const productName = isFee ? (qi.remark || "—") : (qi.product_name_snapshot ?? "—");
  const qty = isFee ? null : (qi.quantity ?? "—");
  const uom = isFee ? "" : (qi.uom ?? "");

  return (
    <tr className="border-t border-gray-100 even:bg-slate-50/50">
      <td className="px-4 py-3 font-medium text-gray-800">
        <div className="flex items-center gap-1.5">
          {isFee && (
            <span className="inline-flex rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
              {tQ("lineAdditional")}
            </span>
          )}
          {productName}
        </div>
      </td>
      <td className="px-4 py-3 text-right text-gray-800">
        {qty != null ? <>{qty} {uom}</> : "—"}
      </td>
      <td className="px-4 py-3 text-right">
        {isFee ? <span className="text-gray-400">—</span> : (
        <div className="font-semibold text-gray-800">
          {qi.unit_price != null
            ? formatCurrency(Number(qi.unit_price), currency, locale)
            : "—"}
        </div>
        )}
        {!isFee && qi.tiers.length > 0 && (
          <div className="mt-1">
            <button type="button" onClick={() => setShowTiers(!showTiers)}
              className="text-[10px] font-medium text-[#00505a] hover:underline">
              {tQ("tiers")} ({qi.tiers.length}) {showTiers ? "▲" : "▼"}
            </button>
            {showTiers && (
              <div className="mt-1 space-y-0.5 text-left">
                {[...qi.tiers].sort((a, b) => a.min_qty - b.min_qty).map((tier, idx, sorted) => {
                  const next = sorted[idx + 1];
                  const label = next ? `${tier.min_qty}~${next.min_qty - 1}` : `≥${tier.min_qty}`;
                  return (
                    <div key={idx} className="text-[10px] text-gray-500">
                      <span className="inline-block w-16">{label}</span>
                      <span className="font-semibold text-[#00505a]">{formatCurrency(Number(tier.unit_price), currency, locale)}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {qi.moq != null ? Number(qi.moq) : "—"}
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {qi.cbm_per_unit != null ? Number(qi.cbm_per_unit) : "—"}
      </td>
      <td className="px-4 py-3 text-right text-gray-600">
        {qi.gross_weight_per_unit != null ? Number(qi.gross_weight_per_unit) : "—"}
      </td>
      <td className="px-4 py-3 text-right font-semibold text-gray-800">
        {qi.line_amount != null
          ? formatCurrency(Number(qi.line_amount), currency, locale)
          : "—"}
      </td>
    </tr>
  );
}

export default function RfqDetailPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_READ]}>
      <RfqDetailContent />
    </RouteGuard>
  );
}
