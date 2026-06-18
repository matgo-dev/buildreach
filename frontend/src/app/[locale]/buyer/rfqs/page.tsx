"use client";

import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Loader2, FileText, Package, ShoppingCart, Download } from "lucide-react";

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
import { useCartStore } from "@/stores/cartStore";
import Link from "next/link";

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
  const cartCount = useCartStore((s) => s.count);

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
      await exportQuotePdf(rfqId);
    } catch (err) {
      showError(err);
    } finally {
      setExportingId(null);
    }
  }, [showError]);

  // 按状态渲染操作按钮
  const renderActions = useCallback((rfq: { id: number; status: string }) => {
    const btns: React.ReactNode[] = [];

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
          className="inline-flex items-center gap-1 text-xs font-medium text-[#00505a] hover:underline disabled:opacity-50"
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
          className="text-xs font-medium text-blue-600 hover:underline"
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
          className="text-xs font-medium text-[#00505a] hover:underline"
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
          className="text-xs font-medium text-amber-600 hover:underline"
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
          className="text-xs font-medium text-red-600 hover:underline"
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
          className="text-xs font-medium text-[#00505a] hover:underline"
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
          className="text-xs font-medium text-red-600 hover:underline"
        >
          {tQ("reject")}
        </button>,
      );
    }

    return <div className="flex items-center justify-end gap-3">{btns}</div>;
  }, [t, tQ, locale, router, hasPermission, openConfirm, execAction, exportingId, handleExport]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold text-gray-800">{t("title")}</h1>
        <Link
          href={`/${locale}/buyer/cart`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#00505a]/30 px-3 py-1.5 text-sm font-medium text-[#00505a] transition-colors hover:bg-[#00505a] hover:text-white"
        >
          <ShoppingCart className="h-4 w-4" />
          {t("goToCart")}
          {cartCount > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#00505a] px-1 text-xs text-white">
              {cartCount}
            </span>
          )}
        </Link>
      </div>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
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
      </div>

      {/* 列表 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {/* 表头 — 与询价篮表头对齐: px-5 py-3 bg-slate-50 */}
        <div className="flex items-center gap-3 border-b border-gray-200 bg-slate-50 px-5 py-3 text-xs text-gray-500">
          <span className="flex-1 font-medium">{t("productSummary")}</span>
          <span className="w-24 text-center font-medium">{t("totalQty")}</span>
          <span className="w-24 text-center font-medium">{t("status")}</span>
          <span className="w-28 text-center font-medium">{t("submitTime")}</span>
          <span className="w-32 text-right font-medium">{t("actions")}</span>
        </div>

        {isLoading ? (
          <div className="flex h-60 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#00505a]" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center text-gray-400">
            <FileText className="mb-3 h-12 w-12 text-gray-200" />
            <p className="text-sm">{t("emptyList")}</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {data.items.map((rfq) => {
              const summary = buildProductSummary(rfq.items);

              return (
                <div
                  key={rfq.id}
                  onClick={() => router.push(`/${locale}/buyer/rfqs/${rfq.id}`)}
                  className="flex cursor-pointer items-center gap-3 px-5 py-4 transition-colors hover:bg-blue-50/30"
                >
                  {/* 缩略图 + 商品信息 — 与询价篮行对齐 */}
                  <div className="flex flex-1 items-center gap-4 min-w-0">
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
                  <div className="w-24 shrink-0 text-center">
                    <span className="text-sm text-gray-600">{t("itemCount", { count: rfq.items.length })}</span>
                  </div>

                  {/* 状态 */}
                  <div className="w-24 shrink-0 text-center">
                    <RfqStatusBadge status={rfq.status} />
                  </div>

                  {/* 时间 */}
                  <div className="w-28 shrink-0 text-center">
                    <span className="text-xs text-gray-400">
                      {rfq.created_at ? formatRelativeTime(rfq.created_at, locale) : "—"}
                    </span>
                  </div>

                  {/* 操作 */}
                  <div className="w-32 shrink-0">
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
