"use client";

import { useTranslations } from "next-intl";
import { ListFilter, X } from "lucide-react";

interface Props {
  sort: string;
  total: number;
  onSortChange: (sort: string) => void;
  hasActiveFilters: boolean;
  onClearAll: () => void;
}

/**
 * 筛选结果工具栏 — FilterBar 下方、ProductGrid 上方。
 * 显示排序、商品总数、清除筛选。
 */
export function SortBar({ sort, total, onSortChange, hasActiveFilters, onClearAll }: Props) {
  const t = useTranslations("mall");

  return (
    <div className="flex items-center justify-between rounded-lg bg-white border border-line px-4 py-2.5 shadow-mall-sm">
      <div className="flex items-center gap-2">
        <ListFilter className="h-3.5 w-3.5 text-muted" />
        {/* 默认排序：最新上架 */}
        <button
          onClick={() => onSortChange("newest")}
          className="h-8 rounded-md px-3 text-[13px] font-semibold bg-teal-700 text-white shadow-sm"
        >
          {t("sortNewest")}
        </button>

        {/* 清除筛选 */}
        {hasActiveFilters && (
          <>
            <div className="h-4 w-px bg-gray-200" />
            <button
              onClick={onClearAll}
              className="flex items-center gap-1 h-8 rounded-md px-3 text-[13px] font-semibold text-red-600 hover:bg-red-50 transition-all"
            >
              <X className="h-3 w-3" />
              {t("clearFilters")}
            </button>
          </>
        )}
      </div>

      {/* 商品总数 */}
      <span className="text-[13px] text-muted font-medium whitespace-nowrap">
        {t("totalProducts", { count: total })}
      </span>
    </div>
  );
}
