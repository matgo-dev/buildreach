"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { X, ListFilter } from "lucide-react";
import useSWR from "swr";

import type { CategoryTreeNode } from "@/lib/api/categories";
import { listBrands } from "@/lib/api/products";
import { FilterPanel } from "./FilterPanel";

interface Props {
  sort: string;
  featured: boolean;
  supplyMode: string;
  total: number;
  activeCategoryCode: string;
  categoryTree: CategoryTreeNode[];
  brand: string;
  onSortChange: (sort: string) => void;
  onFeaturedToggle: () => void;
  onSupplyModeChange: (mode: string) => void;
  onCategoryChange: (code: string) => void;
  onBrandChange: (brand: string) => void;
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
  brand,
  onSortChange,
  onFeaturedToggle,
  onSupplyModeChange,
  onCategoryChange,
  onBrandChange,
  onClearAll,
  hasActiveFilters,
}: Props) {
  const t = useTranslations("mall");

  // 品牌列表
  const { data: brands = [] } = useSWR<string[]>(
    `/api/v1/products/brands?cat=${activeCategoryCode}`,
    () => listBrands(activeCategoryCode || undefined),
    { revalidateOnFocus: false },
  );

  const brandItems = useMemo(
    () => brands.map((b) => ({ key: b, label: b })),
    [brands],
  );

  const selectedBrands = useMemo(
    () => (brand ? brand.split(",") : []),
    [brand],
  );

  // 品牌单选：点击直接筛选（替换当前选中）
  const handleBrandSelect = (key: string) => {
    // 再次点击取消选中
    if (selectedBrands.length === 1 && selectedBrands[0] === key) {
      onBrandChange("");
    } else {
      onBrandChange(key);
    }
  };

  // 品牌多选确认
  const handleBrandMultiSelect = (keys: string[]) => {
    onBrandChange(keys.join(","));
  };

  // L1 品类列表
  const categoryItems = useMemo(
    () => categoryTree.map((c) => ({ key: c.code, label: c.name })),
    [categoryTree],
  );

  const handleCategorySelect = (code: string) => {
    // 再次点击取消选中
    if (activeCategoryCode === code) {
      onCategoryChange("");
    } else {
      onCategoryChange(code);
    }
  };

  return (
    <div className="rounded-xl border border-line bg-white shadow-mall-sm">
      {/* 品牌+品类筛选行 — 移动端隐藏，桌面端展示 */}
      <div className="hidden lg:block">
        {/* 品牌筛选行 */}
        {brandItems.length > 0 && (
          <FilterPanel
            label={t("filterBrand") + "："}
            items={brandItems}
            selected={selectedBrands}
            onSelect={handleBrandSelect}
            onMultiSelect={handleBrandMultiSelect}
            allLabel={t("filterAllBrands")}
            onClearAll={() => onBrandChange("")}
          />
        )}

        {/* 品类筛选行 */}
        {categoryItems.length > 0 && (
          <>
            {brandItems.length > 0 && <div className="border-t border-line" />}
            <FilterPanel
              label={t("filterCategory") + "："}
              items={categoryItems}
              selected={activeCategoryCode ? [activeCategoryCode] : []}
              onSelect={handleCategorySelect}
              allLabel={t("filterAllCategories")}
              onClearAll={() => onCategoryChange("")}
            />
          </>
        )}

        {/* 分隔线 */}
        <div className="border-t border-line" />
      </div>

      {/* 行2: 排序 + 快筛 + 清除 | 商品总数 */}
      <div className="px-3 sm:px-5 py-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
          <ListFilter className="h-3.5 w-3.5 text-muted mr-0.5 shrink-0" />

          {/* 最新上架 */}
          <button
            onClick={() => onSortChange("newest")}
            className={`shrink-0 whitespace-nowrap h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              sort === "newest"
                ? "bg-teal-900 text-white shadow-sm"
                : "text-ink hover:bg-teal-50 hover:text-teal-900"
            }`}
          >
            {t("sortNewest")}
          </button>

          <div className="h-4 w-px bg-gray-200 shrink-0" />

          {/* 精选推荐 */}
          <button
            onClick={onFeaturedToggle}
            className={`shrink-0 whitespace-nowrap h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
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
            className={`shrink-0 whitespace-nowrap h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
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
            className={`shrink-0 whitespace-nowrap h-[28px] rounded-md px-2.5 text-[12px] font-semibold transition-all ${
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
              <div className="h-4 w-px bg-gray-200 shrink-0" />
              <button
                onClick={onClearAll}
                className="shrink-0 whitespace-nowrap flex items-center gap-1 h-[28px] rounded-md px-2.5 text-[12px] font-semibold text-red-600 hover:bg-red-50 transition-all"
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
