"use client";

import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";
import { useCallback, useState } from "react";
import { mutate } from "swr";

import type { CategoryTreeNode } from "@/lib/api/categories";
import { useAuthStore } from "@/stores/authStore";
import { SectionTitle } from "./SectionTitle";
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
 * 筛选栏 — 参考 HTML 设计稿 .filters + .chip-row
 *
 * 行1: 搜索框 | 认证下拉 | 筛选按钮(最右)
 * 行2: 品类 chip,点击联动左侧品类导航
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
    // 延迟刷新最近搜索缓存，等后端 BackgroundTask 写入完成
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
    <div
      className="rounded-xl border border-line bg-white shadow-mall-sm"
    >
      {/* 区块标题 */}
      <div className="px-6 pt-5 pb-3">
        <SectionTitle
          sub={t("sectionFeatured")}
          right={
            <span className="text-xs font-extrabold text-teal-900">
              {t("totalProducts", { count: total })}
            </span>
          }
        >
          {t("featuredProducts")}
        </SectionTitle>
      </div>

      {/* 筛选行 */}
      <form
        onSubmit={handleSearchSubmit}
        className="px-6 pb-3"
      >
        <div className="grid grid-cols-[1fr_minmax(130px,0.6fr)_auto] gap-2.5 items-center">
          {/* 搜索框 + 最近搜索下拉 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={() => setSearchFocused(true)}
              onClick={() => setSearchFocused(true)}
              placeholder={t("searchPlaceholder")}
              className="h-[42px] w-full rounded-[7px] border border-line-strong bg-white pl-9 pr-3 text-[14.5px] text-ink placeholder-muted outline-none transition-colors focus:border-teal-700 focus:ring-[3px] focus:ring-teal-700/[.14]"
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
            {/* 最近搜索下拉面板 */}
            {isBuyer && (
              <RecentSearches
                visible={searchFocused}
                onSelect={handleSelectSearch}
                onClose={() => setSearchFocused(false)}
              />
            )}
          </div>

          {/* 认证下拉 */}
          <select
            value={certification}
            onChange={(e) => onCertificationChange(e.target.value)}
            className={`h-[42px] rounded-[7px] border border-line-strong bg-white px-3 text-[14px] outline-none transition-colors focus:border-teal-700 focus:ring-[3px] focus:ring-teal-700/[.14] ${
              certification ? "text-ink" : "text-muted"
            }`}
          >
            <option value="">{t("filterCertAll")}</option>
            {certificationOptions.map((cert) => (
              <option key={cert} value={cert}>{cert}</option>
            ))}
          </select>

{/* 筛选按钮 — 最右 */}
          <MallButton type="submit" variant="teal" className="h-[42px] shrink-0">
            {t("filterSearch")}
          </MallButton>
        </div>
      </form>

      {/* 筛选标签行：精选 + 履约模式 */}
      <div className="px-6 pb-2 flex items-center gap-2">
        <span className="text-xs text-muted mr-1">{t("filterLabel")}:</span>
        <button
          onClick={onFeaturedToggle}
          className={`h-7 rounded-md px-2.5 text-[12px] font-semibold transition-all ${
            featured
              ? "bg-amber-500 text-white shadow-sm"
              : "bg-gray-100 text-ink hover:bg-amber-50 hover:text-amber-700"
          }`}
        >
          {t("featuredOnly")}
        </button>
        <div className="h-4 w-px bg-gray-200" />
        <button
          onClick={() => onSupplyModeChange(supplyMode === "PLATFORM_STOCK" ? "" : "PLATFORM_STOCK")}
          className={`h-7 rounded-md px-2.5 text-[12px] font-semibold transition-all ${
            supplyMode === "PLATFORM_STOCK"
              ? "bg-blue-600 text-white shadow-sm"
              : "bg-gray-100 text-ink hover:bg-blue-50 hover:text-blue-700"
          }`}
        >
          {t("supplyModePlatformStock")}
        </button>
        <button
          onClick={() => onSupplyModeChange(supplyMode === "SUPPLIER_DIRECT" ? "" : "SUPPLIER_DIRECT")}
          className={`h-7 rounded-md px-2.5 text-[12px] font-semibold transition-all ${
            supplyMode === "SUPPLIER_DIRECT"
              ? "bg-emerald-600 text-white shadow-sm"
              : "bg-gray-100 text-ink hover:bg-emerald-50 hover:text-emerald-700"
          }`}
        >
          {t("supplyModeSupplierDirect")}
        </button>
      </div>

      {/* 品类 chip 行 */}
      <div className="px-6 pb-4 flex flex-wrap gap-1.5">
        <button
          onClick={() => onCategoryChange("")}
          className={`h-7 rounded-md px-2.5 text-[12px] font-semibold transition-all ${
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
            className={`h-7 rounded-md px-2.5 text-[12px] font-semibold transition-all ${
              activeCategoryCode === cat.code
                ? "bg-teal-900 text-white shadow-sm"
                : "bg-gray-100 text-ink hover:bg-teal-50 hover:text-teal-900"
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
