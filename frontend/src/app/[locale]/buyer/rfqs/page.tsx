"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { Loader2, FileText, Eye } from "lucide-react";
import Link from "next/link";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import Pagination from "@/components/ui/Pagination";
import { RfqStatusBadge } from "@/components/rfq/RfqStatusBadge";
import { listRfqs, type RfqListResponse } from "@/lib/api/rfqs";
import { formatDate } from "@/lib/formatters";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = ["", "SUBMITTED", "QUOTED", "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"];

function RfqListContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [mineOnly, setMineOnly] = useState(false);

  const swrKey = `rfqs-${page}-${statusFilter}-${mineOnly}`;
  const { data, isLoading } = useSWR<RfqListResponse>(
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

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-800">{t("title")}</h1>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
        {/* 范围 tab */}
        <div className="flex rounded-lg border border-gray-200">
          <button
            type="button"
            onClick={() => { setMineOnly(false); setPage(1); }}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              !mineOnly ? "bg-[#0D4D4D] text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {t("filterAll")}
          </button>
          <button
            type="button"
            onClick={() => { setMineOnly(true); setPage(1); }}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              mineOnly ? "bg-[#0D4D4D] text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {t("filterMine")}
          </button>
        </div>

        {/* 状态筛选 */}
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="h-8 rounded-lg border border-gray-200 px-3 text-xs outline-none focus:border-[#0D4D4D]"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s ? t(`status_${s}` as Parameters<typeof t>[0]) : t("filterAll")}
            </option>
          ))}
        </select>
      </div>

      {/* 表格 */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {isLoading ? (
          <div className="flex h-60 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#0D4D4D]" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center text-gray-400">
            <FileText className="mb-3 h-12 w-12 text-gray-200" />
            <p className="text-sm">{t("filterAll")}</p>
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
                  className="border-t border-gray-100 transition-colors hover:bg-gray-50"
                >
                  <td className="px-5 py-3">
                    <Link
                      href={`/${locale}/buyer/rfqs/${rfq.id}`}
                      className="font-medium text-[#0D4D4D] hover:underline"
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
                    <Link
                      href={`/${locale}/buyer/rfqs/${rfq.id}`}
                      className="inline-flex items-center gap-1 text-xs font-medium text-[#0D4D4D] transition-colors hover:text-[#0a3d3d]"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      {t("viewDetail")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
