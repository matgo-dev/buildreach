"use client";

import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pages, total, size, onPageChange }: Props) {
  const t = useTranslations("mall");
  if (total === 0) return null;

  const start = (page - 1) * size + 1;
  const end = Math.min(page * size, total);

  // 生成页码数组，最多显示 7 个
  const getPageNumbers = (): (number | "...")[] => {
    if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
    const result: (number | "...")[] = [1];
    if (page > 3) result.push("...");
    const rangeStart = Math.max(2, page - 1);
    const rangeEnd = Math.min(pages - 1, page + 1);
    for (let i = rangeStart; i <= rangeEnd; i++) result.push(i);
    if (page < pages - 2) result.push("...");
    result.push(pages);
    return result;
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3 shadow-mall-sm">
      <span className="text-xs text-gray-500">
        {t("showing", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="flex h-7 w-7 items-center justify-center rounded border border-gray-200 text-gray-500 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        {getPageNumbers().map((p, i) =>
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-1 text-xs text-gray-400">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`flex h-7 min-w-[28px] items-center justify-center rounded border text-xs font-medium transition-colors ${
                p === page
                  ? "border-teal-900 bg-teal-900 text-white"
                  : "border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          className="flex h-7 w-7 items-center justify-center rounded border border-gray-200 text-gray-500 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
