"use client";

import { useTranslations } from "next-intl";
import { Search, X, ListFilter } from "lucide-react";
import { useCallback, useState } from "react";
import { mutate } from "swr";

import type { CategoryTreeNode } from "@/lib/api/categories";
import { useAuthStore } from "@/stores/authStore";
import { MallButton } from "./MallButton";
import { RecentSearches } from "./RecentSearches";

interface Props {
  keyword: string;
  sort: string;
  featured: boolean;
  supplyMode: string;
  certification: string;
  certificationOptions: string[];
  total: number;
  activeCategoryCode: string;
  categoryTree: CategoryTreeNode[];
  onKeywordChange: (keyword: string) => void;
  onSortChange: (sort: string) => void;
  onFeaturedToggle: () => void;
  onSupplyModeChange: (mode: string) => void;
  onCertificationChange: (cert: string) => void;
  onCategoryChange: (code: string) => void;
  onClearAll: () => void;
  hasActiveFilters: boolean;
}

/**
 * 统一筛选栏 — 搜索 + 品类 + 排序/筛选/商品数 三行合一。
 *
 * 行1: 搜索框 | 认证下拉 | 筛选按钮
 * 行2: 品类 chips
 * 行3: 最新上架 | 精选推荐 | 集采 | 直供 | 清除筛选 ... 共N件商品
 */
export function FilterBar({
  keyword,
  sort,
  featured,
  supplyMode,
  certification,
  certificationOptions,
  total,
  activeCategoryCode,
  categoryTree,
  onKeywordChange,
  onSortChange,
  onFeaturedToggle,
  onSupplyModeChange,
  onCertificationChange,
  onCategoryChange,
  onClearAll,
  hasActiveFilters,
}: Props) {
  const t = useTranslations("mall");
  const [inputValue, setInputValue] = useState(keyword);
  const [searchFocused, setSearchFocused] = useState(false);
  const isBuyer = useAuthStore((s) => s.hasRole("BUYER"));

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onKeywordChange(inputValue.trim());
    setSearchFocused(false);
    if (inputValue.trim()) {
      setTimeout(() => mutate("buyer-recent-searches"), 1500);
    }
  };

  const handleSelectSearch = useCallback((kw: string) => {
    setInputValue(kw);
    onKeywordChange(kw);
    setSearchFocused(false);
  }, [onKeywordChange]);

  return (
    <div className="rounded-xl border border-line bg-white shadow-mall-sm">
      {/* 行1: 搜索框 + 认证下拉 + 筛选按钮 */}
      <form onSubmit={handleSearchSubmit} className="px-5 pt-4 pb-3">
        <div className="grid grid-cols-[1fr_minmax(130px,0.5fr)_auto] gap-2.5 items-center">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={() => setSearchFocused(true)}
              onClick={() => setSearchFocused(true)}
              placeholder={t("searchPlaceholder")}
              className="h-[40px] w-full rounded-lg border border-line-strong bg-white pl-9 pr-3 text-[14px] text-ink placeholder-muted outline-none transition-colors focus:border-teal-700 focus:ring-[3px] focus:ring-teal-700/[.14]"
            />
            {keyword && (
              <button
                type="button"
                onClick={() => { setInputValue(""); onKeywordChange(""); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            {isBuyer && (
              <RecentSearches
                visible={searchFocused}
                onSelect={handleSelectSearch}
                onClose={() => setSearchFocused(false)}
              />
            )}
          </div>

          <select
            value={certification}
            onChange={(e) => onCertificationChange(e.target.value)}
            className={`h-[40px] rounded-lg border border-line-strong bg-white px-3 text-[13px] outline-none transition-colors focus:border-teal-700 focus:ring-[3px] focus:ring-teal-700/[.14] ${
              certification ? "text-ink" : "text-muted"
            }`}
          >
            <option value="">{t("filterCertAll")}</option>
            {certificationOptions.map((cert) => (
              <option key={cert} value={cert}>{cert}</option>
            ))}
          </select>

          <MallButton type="submit" variant="teal" className="h-[40px] shrink-0">
            {t("filterSearch")}
          </MallButton>
        </div>
      </form>

      {/* 行2: 品类 chips */}
      <div className="px-5 pb-3 flex flex-wrap gap-1.5">
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

      {/* 行3: 排序 + 快筛 + 清除 | 商品总数 */}
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
