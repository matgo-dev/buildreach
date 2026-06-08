"use client";

import { useTranslations } from "next-intl";
import { useMemo } from "react";

interface PaginationProps {
  current: number;
  total: number;
  totalItems?: number;
  onChange: (page: number) => void;
}

/**
 * 生成页码数组，总页数 >7 时用 -1 表示省略号
 * 始终保留首页、末页、当前页 ± 1
 */
function buildPageNumbers(current: number, total: number): number[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages = new Set<number>();
  pages.add(1);
  pages.add(total);
  for (let i = current - 1; i <= current + 1; i++) {
    if (i >= 1 && i <= total) pages.add(i);
  }

  const sorted = Array.from(pages).sort((a, b) => a - b);
  const result: number[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) {
      result.push(-1); // 省略号占位
    }
    result.push(sorted[i]);
  }
  return result;
}

export default function Pagination({ current, total, totalItems, onChange }: PaginationProps) {
  const t = useTranslations("pagination");
  const pageNumbers = useMemo(() => buildPageNumbers(current, total), [current, total]);

  if (total <= 0) return null;

  return (
    <div className="flex items-center justify-between text-sm text-slate-500">
      {/* 左侧信息 */}
      <div className="flex items-center gap-2">
        {totalItems != null && <span>{t("totalItems", { count: totalItems })}</span>}
        {totalItems != null && <span>·</span>}
        <span>{t("pageInfo", { current, total })}</span>
      </div>

      {/* 右侧页码 */}
      <div className="flex items-center gap-1">
        {/* 上一页 */}
        <button
          disabled={current <= 1}
          onClick={() => onChange(current - 1)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          &lt; {t("prev")}
        </button>

        {/* 页码按钮 */}
        {pageNumbers.map((p, idx) =>
          p === -1 ? (
            <span key={`ellipsis-${idx}`} className="px-1.5 text-slate-400 select-none">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`min-w-[32px] rounded-lg px-2.5 py-1.5 font-medium ${
                p === current
                  ? "bg-blue-600 text-white"
                  : "border border-slate-200 hover:bg-slate-50"
              }`}
            >
              {p}
            </button>
          )
        )}

        {/* 下一页 */}
        <button
          disabled={current >= total}
          onClick={() => onChange(current + 1)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t("next")} &gt;
        </button>
      </div>
    </div>
  );
}
