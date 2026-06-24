"use client";

import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Loader2, FileText, Package, Download, Plus, ShoppingCart, MessageCircle } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { usePermissions } from "@/hooks/usePermissions";
import { useToast } from "@/components/ui/Toast";
import Pagination from "@/components/ui/Pagination";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import {
  listRfqs, submitRfq, cancelRfq, withdrawRfq,
  type RfqListResponse,
} from "@/lib/api/rfqs";
import { acceptRfq, rejectRfq } from "@/lib/api/quotes";
import { exportQuotePdf } from "@/lib/api/quote-export";
import { formatRelativeTime } from "@/lib/formatters";
import { RfqTabNav } from "@/components/rfq/RfqTabNav";
import { useWhatsApp } from "@/hooks/useWhatsApp";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  "", "DRAFT", "SUBMITTED", "QUOTED", "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED",
];

/** 拼商品摘要：前 2 个商品名 + 超出数量 */
function buildProductSummary(items: { product_name_snapshot: string | null }[]): string {
  const names = items
    .map((i) => i.product_name_snapshot)
    .filter(Boolean) as string[];
  if (names.length === 0) return "—";
  const shown = names.slice(0, 2).join("、");
  const extra = names.length > 2 ? ` +${names.length - 2}` : "";
  return shown + extra;
}

function RfqListContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tQ = useTranslations("quote");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();
  const { hasPermission } = usePermissions();
  const wa = useWhatsApp();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [mineOnly, setMineOnly] = useState(false);

  const swrKey = `rfqs-${page}-${statusFilter}-${mineOnly}`;
  const { data, isLoading, mutate } = useSWR<RfqListResponse>(
    swrKey,
    () =>
      listRfqs({
        page,
        page_size: PAGE_SIZE,
        status: statusFilter || undefined,
        mine: mineOnly || undefined,
      }),
    { revalidateOnFocus: false },
  );

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const handlePageChange = useCallback((p: number) => setPage(p), []);

  // 操作状态
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    description: string;
    variant: "primary" | "danger";
    confirmLabel: string;
    action: (() => Promise<void>) | null;
  }>({ open: false, title: "", description: "", variant: "primary", confirmLabel: "", action: null });
  const [actionLoading, setActionLoading] = useState(false);

  const showError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.messageKey) {
      const key = err.messageKey.replace(/^error\./, "");
      try { toast.error(tError(key)); } catch { toast.error(err.message); }
    } else {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [toast, tError]);

  const execAction = useCallback(async (fn: () => Promise<unknown>, successMsg: string) => {
    setActionLoading(true);
    try {
      await fn();
      mutate();
      setConfirmModal((prev) => ({ ...prev, open: false }));
      toast.success(successMsg);
    } catch (err) {
      showError(err);
    } finally {
      setActionLoading(false);
    }
  }, [mutate, toast, showError]);

  const openConfirm = useCallback((
    title: string, description: string, variant: "primary" | "danger",
    confirmLabel: string, action: () => Promise<void>,
  ) => {
    setConfirmModal({ open: true, title, description, variant, confirmLabel, action });
  }, []);

  // 导出报价单
  const [exportingId, setExportingId] = useState<number | null>(null);
  const handleExport = useCallback(async (rfqId: number) => {
    setExportingId(rfqId);
    try {
      const result = await exportQuotePdf(rfqId);
      if (result.status === "generating") {
        toast.warning(tQ("documentGeneratingToast"));
      } else if (result.status === "failed") {
        toast.error(tQ("documentFailedToast"));
      }
    } catch (err) {
      showError(err);
    } finally {
      setExportingId(null);
    }
  }, [showError, toast, tQ]);

  // 按状态渲染操作按钮
  const renderActions = useCallback((rfq: { id: number; status: string }) => {
    const btns: React.ReactNode[] = [];

    // 买方前台按钮样式：小型圆角 pill 按钮
    const btnPrimary = "inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[#00505a] bg-[#00505a] px-3 py-1 text-xs font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d] active:bg-[#002b2b]";
    const btnOutline = "inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[#00505a]/40 px-3 py-1 text-xs font-medium text-[#00505a] shadow-sm transition-colors hover:bg-[#00505a]/5 active:bg-[#00505a]/10";
    const btnDanger = "inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-red-200 px-3 py-1 text-xs font-medium text-red-600 shadow-sm transition-colors hover:bg-red-50 active:bg-red-100";
    const btnWarn = "inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-amber-200 px-3 py-1 text-xs font-medium text-amber-700 shadow-sm transition-colors hover:bg-amber-50 active:bg-amber-100";

    // QUOTED / ACCEPTED 可导出报价单
    if (rfq.status === "QUOTED" || rfq.status === "ACCEPTED") {
      btns.push(
        <button
          key="export"
          type="button"
          disabled={exportingId === rfq.id}
          onClick={(e) => {
            e.stopPropagation();
            handleExport(rfq.id);
          }}
          className={`${btnOutline} disabled:opacity-50`}
        >
          {exportingId === rfq.id ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Download className="h-3 w-3" />
          )}
          {tQ("downloadPdf")}
        </button>,
      );
    }

    if (rfq.status === "DRAFT") {
      btns.push(
        <button
          key="edit"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            router.push(`/${locale}/buyer/rfqs/${rfq.id}/edit`);
          }}
          className={btnOutline}
        >
          {t("edit")}
        </button>,
        <button
          key="submit"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openConfirm(t("submitDraft"), t("submitDraftConfirm"), "primary", t("submitDraft"),
              () => execAction(() => submitRfq(rfq.id), t("submitDraftSuccess")));
          }}
          className={btnPrimary}
        >
          {t("submitDraft")}
        </button>,
      );
    } else if (rfq.status === "SUBMITTED") {
      btns.push(
        <button
          key="withdraw"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openConfirm(t("withdraw"), t("withdrawConfirm"), "primary", t("withdraw"),
              () => execAction(() => withdrawRfq(rfq.id), t("withdrawSuccess")));
          }}
          className={btnWarn}
        >
          {t("withdraw")}
        </button>,
        <button
          key="cancel"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openConfirm(t("cancel"), t("cancelConfirm"), "danger", t("cancel"),
              () => execAction(() => cancelRfq(rfq.id), t("cancelSuccess")));
          }}
          className={btnDanger}
        >
          {t("cancel")}
        </button>,
      );
    } else if (rfq.status === "QUOTED" && hasPermission(Permissions.RFQ_DECIDE)) {
      btns.push(
        <button
          key="accept"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openConfirm(tQ("confirmAcceptTitle"), tQ("confirmAccept"), "primary", tQ("accept"),
              () => execAction(() => acceptRfq(rfq.id), tQ("acceptSuccess")));
          }}
          className={btnPrimary}
        >
          {tQ("accept")}
        </button>,
        <button
          key="reject"
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            openConfirm(tQ("confirmRejectTitle"), tQ("confirmReject"), "danger", tQ("reject"),
              () => execAction(() => rejectRfq(rfq.id), tQ("rejectSuccess")));
          }}
          className={btnDanger}
        >
          {tQ("reject")}
        </button>,
      );
    }

    return <div className="flex items-center justify-end gap-2 whitespace-nowrap">{btns}</div>;
  }, [t, tQ, locale, router, hasPermission, openConfirm, execAction, exportingId, handleExport]);

  return (
    <div className="space-y-4">
      {/* Tab + 列表整体卡片 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {/* Tab 导航：询价篮 / 询价管理 */}
        <RfqTabNav />
        {/* 筛选栏 */}
        <div className="flex flex-wrap items-center gap-4 border-b border-gray-200 px-5 py-3">
          {/* 范围 tab */}
          <div className="flex rounded-lg border border-gray-200">
            <button
              type="button"
              onClick={() => { setMineOnly(false); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                !mineOnly ? "bg-[#00505a] text-white" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t("filterAll")}
            </button>
            <button
              type="button"
              onClick={() => { setMineOnly(true); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                mineOnly ? "bg-[#00505a] text-white" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t("filterMine")}
            </button>
          </div>

          {/* 状态筛选 */}
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-8 rounded-lg border border-gray-200 px-3 text-xs outline-none focus:border-[#00505a]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s ? t(`status_${s}` as Parameters<typeof t>[0]) : t("filterAll")}
              </option>
            ))}
          </select>

          {/* 创建询价单 */}
          <button
            type="button"
            onClick={() => router.push(`/${locale}/buyer/rfqs/create`)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-[#00505a] bg-[#00505a] px-4 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d]"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("createRfq")}
          </button>
        </div>

        {/* 表头 */}
        <div className="grid grid-cols-[1fr_90px_100px_110px_380px] items-center gap-3 border-b border-gray-200 bg-slate-50 px-5 py-3 text-xs text-gray-500">
          <span className="font-medium">{t("productSummary")}</span>
          <span className="text-center font-medium">{t("totalQty")}</span>
          <span className="text-center font-medium">{t("status")}</span>
          <span className="text-center font-medium">{t("submitTime")}</span>
          <span className="text-right font-medium">{t("actions")}</span>
        </div>

        {isLoading ? (
          <div className="flex h-60 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#00505a]" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex min-h-[400px] flex-col items-center justify-center">
            <FileText className="mb-4 h-16 w-16 text-gray-200" />
            <h2 className="text-lg font-semibold text-gray-600">{t("emptyList")}</h2>
            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push(`/${locale}/buyer/cart`)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#00505a] bg-[#00505a] px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#003d3d]"
              >
                <ShoppingCart className="h-4 w-4" />
                {t("goToCart")}
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
          <div className="divide-y divide-gray-100">
            {data.items.map((rfq) => {
              const summary = buildProductSummary(rfq.items);

              return (
                <div
                  key={rfq.id}
                  onClick={() => router.push(`/${locale}/buyer/rfqs/${rfq.id}`)}
                  className="grid grid-cols-[1fr_90px_100px_110px_380px] cursor-pointer items-center gap-3 px-5 py-4 transition-colors hover:bg-blue-50/30"
                >
                  {/* 缩略图 + 商品信息 */}
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="h-[60px] w-[60px] shrink-0 overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
                      {rfq.first_item_image ? (
                        <img
                          src={rfq.first_item_image}
                          alt=""
                          className="h-full w-full object-contain"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-gray-300">
                          <Package className="h-6 w-6" />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <span className="text-xs font-medium text-[#00505a]">{rfq.rfq_no}</span>
                      <p className="mt-0.5 line-clamp-2 text-sm text-gray-700">{summary}</p>
                    </div>
                  </div>

                  {/* 数量 */}
                  <div className="text-center">
                    <span className="text-sm text-gray-600">{t("itemCount", { count: rfq.items.length })}</span>
                  </div>

                  {/* 状态 */}
                  <div className="text-center">
                    <RfqStatusBadge status={rfq.status} />
                  </div>

                  {/* 时间 */}
                  <div className="text-center">
                    <span className="text-xs text-gray-400">
                      {rfq.created_at ? formatRelativeTime(rfq.created_at, locale) : "—"}
                    </span>
                  </div>

                  {/* 操作 */}
                  <div>
                    {renderActions(rfq)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <Pagination
          current={page}
          total={totalPages}
          totalItems={data?.total}
          onChange={handlePageChange}
        />
      )}

      {/* 通用确认弹窗 */}
      <ConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        description={confirmModal.description}
        variant={confirmModal.variant}
        loading={actionLoading}
        confirmLabel={confirmModal.confirmLabel}
        onConfirm={() => confirmModal.action?.()}
        onCancel={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
      />
    </div>
  );
}

export default function RfqListPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_READ]}>
      <RfqListContent />
    </RouteGuard>
  );
}
