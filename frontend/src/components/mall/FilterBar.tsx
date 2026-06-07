"use client";

import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";
import { useState } from "react";

interface Props {
  keyword: string;
  sort: string;
  featured: boolean;
  total: number;
  onKeywordChange: (keyword: string) => void;
  onSortChange: (sort: string) => void;
  onFeaturedToggle: () => void;
  onClearAll: () => void;
  hasActiveFilters: boolean;
}

export function FilterBar({
  keyword,
  sort,
  featured,
  total,
  onKeywordChange,
  onSortChange,
  onFeaturedToggle,
  onClearAll,
  hasActiveFilters,
}: Props) {
  const t = useTranslations("mall");
  const [inputValue, setInputValue] = useState(keyword);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onKeywordChange(inputValue.trim());
  };

  const sortOptions = [
    { value: "newest", label: t("sortNewest") },
    { value: "price_asc", label: t("sortPriceAsc") },
    { value: "price_desc", label: t("sortPriceDesc") },
  ];

  // 占位筛选项（后端暂无支持）
  const placeholderFilters = [
    t("filterPrice"),
    t("filterMoq"),
    t("filterCertification"),
    t("filterDelivery"),
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        {/* 搜索框 */}
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="h-8 w-48 rounded-lg border border-gray-200 bg-gray-50 pl-8 pr-3 text-xs text-gray-700 placeholder-gray-400 focus:border-[#0D4D4D] focus:outline-none focus:ring-1 focus:ring-[#0D4D4D]/20"
            />
          </div>
          {keyword && (
            <button
              type="button"
              onClick={() => {
                setInputValue("");
                onKeywordChange("");
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </form>

        {/* 分隔线 */}
        <div className="hidden h-5 w-px bg-gray-200 lg:block" />

        {/* 排序 */}
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-8 rounded-lg border border-gray-200 bg-gray-50 px-2.5 text-xs text-gray-600 focus:border-[#0D4D4D] focus:outline-none"
        >
          {sortOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* 精选 */}
        <button
          onClick={onFeaturedToggle}
          className={`h-8 rounded-full px-3 text-xs font-medium transition-colors ${
            featured
              ? "bg-[#FF6B35] text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          ⭐ {t("featuredOnly")}
        </button>

        {/* 占位筛选 */}
        {placeholderFilters.map((label) => (
          <button
            key={label}
            disabled
            title={t("comingSoon")}
            className="h-8 cursor-not-allowed rounded-full bg-gray-100 px-3 text-xs text-gray-400"
          >
            {label} ▾
          </button>
        ))}

        {/* 右侧：总数 + 清除 */}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs font-semibold text-[#0D4D4D]">
            {t("totalProducts", { count: total })}
          </span>
          {hasActiveFilters && (
            <button
              onClick={onClearAll}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-[#FF6B35] transition-colors"
            >
              <X className="h-3 w-3" />
              {t("clearFilters")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
