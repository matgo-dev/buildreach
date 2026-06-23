"use client";

import { useTranslations } from "next-intl";
import { X, ListFilter } from "lucide-react";

import type { CategoryTreeNode } from "@/lib/api/categories";

interface Props {
  sort: string;
  featured: boolean;
  supplyMode: string;
  total: number;
  activeCategoryCode: string;
  categoryTree: CategoryTreeNode[];
  onSortChange: (sort: string) => void;
  onFeaturedToggle: () => void;
  onSupplyModeChange: (mode: string) => void;
  onCategoryChange: (code: string) => void;
  onClearAll: () => void;
  hasActiveFilters: boolean;
}

/**
 * 统一筛选栏 — 品类 chips + 排序/筛选/商品数。
 *
 * 行1: 品类 chips
 * 行2: 最新上架 | 精选推荐 | 集采 | 直供 | 清除筛选 ... 共N件商品
 */
export function FilterBar({
  sort,
  featured,
  supplyMode,
  total,
  activeCategoryCode,
  categoryTree,
  onSortChange,
  onFeaturedToggle,
  onSupplyModeChange,
  onCategoryChange,
  onClearAll,
  hasActiveFilters,
}: Props) {
  const t = useTranslations("mall");

  return (
    <div className="rounded-xl border border-line bg-white shadow-mall-sm">
      {/* 行1: 品类 chips */}
      <div className="px-5 pt-3 pb-3 flex flex-wrap gap-1.5">
        <button
          onClick={() => onCategoryChange("")}
          className={`h-[30px] rounded-full px-3 text-[12px] font-semibold transition-all ${
            !activeCategoryCode
              ? "bg-teal-900 text-white shadow-sm"
              : "bg-gray-100 text-ink hover:bg-teal-50 hover:text-teal-900"
          }`}
        >
          {t("chipAll")}
        </button>
        {categoryTree.map((cat) => (
          <button
            key={cat.code}
            onClick={() => { if (cat.code !== activeCategoryCode) onCategoryChange(cat.code); }}
            className={`h-[30px] rounded-full px-3 text-[12px] font-semibold transition-all ${
              activeCategoryCode === cat.code
                ? "bg-teal-900 text-white shadow-sm"
                : "bg-gray-100 text-ink hover:bg-teal-50 hover:text-teal-900"
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>

      {/* 分隔线 */}
      <div className="border-t border-line" />

      {/* 行2: 排序 + 快筛 + 清除 | 商品总数 */}
      <div className="px-5 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <ListFilter className="h-3.5 w-3.5 text-muted mr-0.5" />

          {/* 最新上架 */}
          <button
            onClick={() => onSortChange("newest")}
            className={`h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              sort === "newest"
                ? "bg-teal-900 text-white shadow-sm"
                : "text-ink hover:bg-teal-50 hover:text-teal-900"
            }`}
          >
            {t("sortNewest")}
          </button>

          <div className="h-4 w-px bg-gray-200" />

          {/* 精选推荐 */}
          <button
            onClick={onFeaturedToggle}
            className={`h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              featured
                ? "bg-amber-500 text-white shadow-sm"
                : "text-ink hover:bg-amber-50 hover:text-amber-700"
            }`}
          >
            {t("featuredOnly")}
          </button>

          {/* 集采 */}
          <button
            onClick={() => onSupplyModeChange(supplyMode === "PLATFORM_STOCK" ? "" : "PLATFORM_STOCK")}
            className={`h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              supplyMode === "PLATFORM_STOCK"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-ink hover:bg-blue-50 hover:text-blue-700"
            }`}
          >
            {t("supplyModePlatformStock")}
          </button>

          {/* 直供 */}
          <button
            onClick={() => onSupplyModeChange(supplyMode === "SUPPLIER_DIRECT" ? "" : "SUPPLIER_DIRECT")}
            className={`h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              supplyMode === "SUPPLIER_DIRECT"
                ? "bg-emerald-600 text-white shadow-sm"
                : "text-ink hover:bg-emerald-50 hover:text-emerald-700"
            }`}
          >
            {t("supplyModeSupplierDirect")}
          </button>

          {/* 清除筛选 */}
          {hasActiveFilters && (
            <>
              <div className="h-4 w-px bg-gray-200" />
              <button
                onClick={onClearAll}
                className="flex items-center gap-1 h-[28px] rounded-md px-2.5 text-[12px] font-semibold text-red-600 hover:bg-red-50 transition-all"
              >
                <X className="h-3 w-3" />
                {t("clearFilters")}
              </button>
            </>
          )}
        </div>

        {/* 商品总数 */}
        <span className="text-[12px] text-muted font-medium whitespace-nowrap">
          {t("totalProducts", { count: total })}
        </span>
      </div>
    </div>
  );
}
