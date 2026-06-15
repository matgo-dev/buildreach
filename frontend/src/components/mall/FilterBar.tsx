"use client";

import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";
import { useState } from "react";

import type { CategoryTreeNode } from "@/lib/api/categories";
import { SectionTitle } from "./SectionTitle";
import { MallButton } from "./MallButton";

interface Props {
  keyword: string;
  sort: string;
  featured: boolean;
  supplyMode: string;
  total: number;
  activeCategoryCode: string;
  categoryTree: CategoryTreeNode[];
  onKeywordChange: (keyword: string) => void;
  onSortChange: (sort: string) => void;
  onFeaturedToggle: () => void;
  onSupplyModeChange: (mode: string) => void;
  onCategoryChange: (code: string) => void;
  onClearAll: () => void;
  hasActiveFilters: boolean;
}

/**
 * 筛选栏 — 参考 HTML 设计稿 .filters + .chip-row
 *
 * 行1: 搜索框 | 品类下拉 | 认证下拉 | 交期下拉 | 筛选按钮(最右)
 * 行2: 品类 chip,点击联动左侧品类导航
 */
export function FilterBar({
  keyword,
  sort,
  featured,
  supplyMode,
  total,
  activeCategoryCode,
  categoryTree,
  onKeywordChange,
  onSortChange,
  onFeaturedToggle,
  onSupplyModeChange,
  onCategoryChange,
  onClearAll,
  hasActiveFilters,
}: Props) {
  const t = useTranslations("mall");
  const [inputValue, setInputValue] = useState(keyword);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onKeywordChange(inputValue.trim());
  };

  return (
    <div
      className="rounded-xl border border-line bg-white shadow-mall-sm overflow-hidden"
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
        <div className="grid grid-cols-[minmax(180px,1.2fr)_repeat(3,minmax(130px,0.7fr))_auto] gap-2.5 items-center">
          {/* 搜索框 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
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
          </div>

          {/* 品类下拉 */}
          <select
            value={activeCategoryCode}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="h-[42px] rounded-[7px] border border-line-strong bg-white px-3 text-[14px] text-ink outline-none transition-colors focus:border-teal-700 focus:ring-[3px] focus:ring-teal-700/[.14]"
          >
            <option value="">{t("filterAllCat")}</option>
            {categoryTree.map((cat) => (
              <option key={cat.code} value={cat.code}>{cat.name}</option>
            ))}
          </select>

          {/* 认证下拉(占位) */}
          <select
            disabled
            className="h-[42px] rounded-[7px] border border-line-strong bg-white px-3 text-[14px] text-gray-300 outline-none cursor-not-allowed"
            title={t("comingSoon")}
          >
            <option>{t("filterCertAll")}</option>
          </select>

          {/* 交期下拉(占位) */}
          <select
            disabled
            className="h-[42px] rounded-[7px] border border-line-strong bg-white px-3 text-[14px] text-gray-300 outline-none cursor-not-allowed"
            title={t("comingSoon")}
          >
            <option>{t("filterDeliveryAll")}</option>
          </select>

          {/* 筛选按钮 — 最右 */}
          <MallButton type="submit" variant="teal" className="h-[42px] shrink-0">
            {t("filterSearch")}
          </MallButton>
        </div>
      </form>

      {/* chip 行: 精选 + 品类联动 */}
      <div className="px-6 pb-4 flex flex-wrap gap-2">
        {/* 精选推荐 */}
        <button
          onClick={onFeaturedToggle}
          className={`h-8 rounded-full px-3 text-[12.5px] font-extrabold transition-all ${
            featured
              ? "text-white border-transparent"
              : "bg-white text-ink border border-line hover:border-gold hover:bg-gold-soft"
          }`}
          style={featured ? {
            background: "linear-gradient(135deg, #f0b734, #e3a615, #c1850b)",
            boxShadow: "0 4px 12px rgba(193,133,11,.3)",
          } : undefined}
        >
          ⭐ {t("featuredOnly")}
        </button>

        {/* 履约模式 chips */}
        <div className="h-8 w-px bg-line self-center" />
        <button
          onClick={() => onSupplyModeChange(supplyMode === "PLATFORM_STOCK" ? "" : "PLATFORM_STOCK")}
          className={`h-8 rounded-full px-3 text-[12.5px] font-extrabold transition-all ${
            supplyMode === "PLATFORM_STOCK"
              ? "bg-blue-600 text-white border-transparent shadow-sm"
              : "bg-white text-ink border border-line hover:border-blue-500 hover:bg-blue-50"
          }`}
        >
          📦 {t("supplyModePlatformStock")}
        </button>
        <button
          onClick={() => onSupplyModeChange(supplyMode === "SUPPLIER_DIRECT" ? "" : "SUPPLIER_DIRECT")}
          className={`h-8 rounded-full px-3 text-[12.5px] font-extrabold transition-all ${
            supplyMode === "SUPPLIER_DIRECT"
              ? "bg-emerald-600 text-white border-transparent shadow-sm"
              : "bg-white text-ink border border-line hover:border-emerald-500 hover:bg-emerald-50"
          }`}
        >
          🏭 {t("supplyModeSupplierDirect")}
        </button>

        {/* 分隔线 */}
        <div className="h-8 w-px bg-line self-center" />

        {/* 全部品类 */}
        <button
          onClick={() => onCategoryChange("")}
          className={`h-8 rounded-full px-3 text-[12.5px] font-extrabold transition-all ${
            !activeCategoryCode
              ? "text-white border-transparent"
              : "bg-white text-ink border border-line hover:border-teal-700 hover:bg-teal-50"
          }`}
          style={!activeCategoryCode ? {
            background: "linear-gradient(135deg, #07808b, #00505a, #003f46)",
            boxShadow: "0 4px 12px rgba(0,63,70,.22)",
          } : undefined}
        >
          {t("chipAll")}
        </button>
        {categoryTree.map((cat) => (
          <button
            key={cat.code}
            onClick={() => onCategoryChange(cat.code === activeCategoryCode ? "" : cat.code)}
            className={`h-8 rounded-full px-3 text-[12.5px] font-extrabold transition-all ${
              activeCategoryCode === cat.code
                ? "text-white border-transparent"
                : "bg-white text-ink border border-line hover:border-teal-700 hover:bg-teal-50"
            }`}
            style={activeCategoryCode === cat.code ? {
              background: "linear-gradient(135deg, #07808b, #00505a, #003f46)",
              boxShadow: "0 4px 12px rgba(0,63,70,.22)",
            } : undefined}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
