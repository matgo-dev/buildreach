"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { Loader2, FileText, FileEdit, Plus } from "lucide-react";
import Link from "next/link";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import Pagination from "@/components/ui/Pagination";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { ApiError } from "@/lib/api";
import { listRfqs, claimRfq, type RfqListResponse } from "@/lib/api/rfqs";
import { formatDate } from "@/lib/formatters";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  "", "DRAFT", "SUBMITTED", "PROCESSING", "QUOTED",
  "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED",
];

function OperatorRfqListContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tError = useTranslations("error");
  const toast = useToast();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [mineFilter, setMineFilter] = useState(false);

  const swrKey = `operator-rfqs-${page}-${statusFilter}-${mineFilter}`;
  const { data, isLoading, mutate } = useSWR<RfqListResponse>(
    swrKey,
    () =>
      listRfqs({
        page,
        page_size: PAGE_SIZE,
        status: statusFilter || undefined,
        mine: mineFilter || undefined,
      }),
    { revalidateOnFocus: false },
  );

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const handlePageChange = useCallback((p: number) => setPage(p), []);

  // 受理确认
  const [claimTarget, setClaimTarget] = useState<number | null>(null);
  const [claiming, setClaiming] = useState(false);

  const showError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.messageKey) {
      const key = err.messageKey.replace(/^error\./, "");
      try { toast.error(tError(key)); } catch { toast.error(err.message); }
    } else {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }, [toast, tError]);

  const handleClaim = useCallback(async () => {
    if (!claimTarget) return;
    setClaiming(true);
    try {
      await claimRfq(claimTarget);
      mutate();
      setClaimTarget(null);
      toast.success(t("claimSuccess"));
    } catch (err) {
      showError(err);
    } finally {
      setClaiming(false);
    }
  }, [claimTarget, mutate, toast, t, showError]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">{t("operatorRfqTitle")}</h1>
        <Link
          href={`/${locale}/operator/rfqs/create`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          {t("createOnBehalf")}
        </Link>
      </div>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="h-8 rounded-lg border border-gray-200 px-3 text-xs outline-none focus:border-blue-500"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s ? t(`status_${s}` as Parameters<typeof t>[0]) : t("filterAll")}
            </option>
          ))}
        </select>
        <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={mineFilter}
            onChange={(e) => { setMineFilter(e.target.checked); setPage(1); }}
            className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          {t("filterMyCreated")}
        </label>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {isLoading ? (
          <div className="flex h-60 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center text-gray-400">
            <FileText className="mb-3 h-12 w-12 text-gray-200" />
            <p className="text-sm">{t("emptyList")}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-5 py-3 font-medium">{t("rfqNo")}</th>
                <th className="px-5 py-3 font-medium">{t("itemCount", { count: "" })}</th>
                <th className="px-5 py-3 font-medium">{t("status")}</th>
                <th className="px-5 py-3 font-medium">{t("submitTime")}</th>
                <th className="px-5 py-3 font-medium text-right">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((rfq) => (
                <tr
                  key={rfq.id}
                  className="border-t border-gray-100 transition-colors even:bg-slate-50/50 hover:bg-blue-50/50 cursor-pointer"
                  onClick={() => router.push(`/${locale}/operator/rfqs/${rfq.id}`)}
                >
                  <td className="px-5 py-3">
                    <Link
                      href={`/${locale}/operator/rfqs/${rfq.id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {rfq.rfq_no}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-gray-600">
                    {t("itemCount", { count: rfq.items.length })}
                  </td>
                  <td className="px-5 py-3">
                    <RfqStatusBadge status={rfq.status} />
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {rfq.created_at ? formatDate(rfq.created_at, locale) : "—"}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex items-center justify-end gap-3" onClick={(e) => e.stopPropagation()}>
                      {rfq.status === "SUBMITTED" && (
                        <button
                          type="button"
                          onClick={() => setClaimTarget(rfq.id)}
                          className="text-xs font-medium text-blue-600 hover:underline"
                        >
                          {t("claim")}
                        </button>
                      )}
                      {rfq.status === "PROCESSING" && (
                        <>
                          <Link
                            href={`/${locale}/operator/rfqs/${rfq.id}`}
                            className="text-xs font-medium text-gray-600 hover:underline"
                          >
                            {t("editRfqItems")}
                          </Link>
                          <Link
                            href={`/${locale}/operator/rfqs/${rfq.id}/quote`}
                            className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
                          >
                            <FileEdit className="h-3.5 w-3.5" />
                            {t("quoteBackfill")}
                          </Link>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <Pagination
          current={page}
          total={totalPages}
          totalItems={data?.total}
          onChange={handlePageChange}
        />
      )}

      {/* 受理确认弹窗 */}
      <ConfirmModal
        open={claimTarget !== null}
        title={t("claim")}
        description={t("claimConfirm")}
        variant="primary"
        loading={claiming}
        confirmLabel={t("claim")}
        onConfirm={handleClaim}
        onCancel={() => setClaimTarget(null)}
      />
    </div>
  );
}

export default function OperatorRfqListPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_READ]}>
      <OperatorRfqListContent />
    </RouteGuard>
  );
}
