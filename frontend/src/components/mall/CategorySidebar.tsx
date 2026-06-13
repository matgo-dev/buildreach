"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronRight, SlidersHorizontal, Star } from "lucide-react";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";

function categoryContainsCode(category: CategoryTreeNode, code: string): boolean {
  if (category.code === code) return true;
  return (category.children || []).some((child) => categoryContainsCode(child, code));
}

/**
 * 商城左侧品类导航侧栏,商品列表页和详情页共用。
 * 点击品类跳转到 /mall?cat=xxx。
 */
export function CategorySidebar({
  activeCategoryCode = "",
  showQuickLinks = false,
  showFeatured = false,
  onFeaturedToggle,
}: {
  /** 当前选中的品类 code */
  activeCategoryCode?: string;
  /** 是否显示 Quick Links 区域 */
  showQuickLinks?: boolean;
  /** 精选筛选是否激活 */
  showFeatured?: boolean;
  /** 精选按钮点击回调,不传则跳转到 /mall?featured=true */
  onFeaturedToggle?: () => void;
}) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const { tree: categoryTree, isLoading: loadingCategories } = useCategoryTree();

  const [hoveredLevel1, setHoveredLevel1] = useState("");
  const [expandedLevel1, setExpandedLevel1] = useState("");

  const handleCategoryClick = (code: string, closeHover = true) => {
    const next = activeCategoryCode === code ? "" : code;
    router.push(`/${locale}/mall${next ? `?cat=${next}` : ""}`, { scroll: false });
    if (closeHover) setHoveredLevel1("");
  };

  const handleMobileLevel1Click = (category: CategoryTreeNode) => {
    handleCategoryClick(category.code, false);
    setExpandedLevel1((prev) => (prev === category.code ? "" : category.code));
  };

  const categoryButtonClass = (category: CategoryTreeNode) => {
    const inSelectedPath = activeCategoryCode && categoryContainsCode(category, activeCategoryCode);
    if (activeCategoryCode === category.code || inSelectedPath) {
      return "bg-blue-50 text-[#0D4D4D] font-semibold";
    }
    return "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]";
  };


  return (
    <aside className="lg:w-52 shrink-0 lg:sticky lg:top-4 lg:self-start z-40">
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        {/* Desktop: hover 飞出二级面板 */}
        <div
          className="relative hidden lg:block"
          onMouseLeave={() => setHoveredLevel1("")}
        >
          <ul className="space-y-1">
            <li>
              <button
                onClick={() => handleCategoryClick("")}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-semibold transition-all relative flex items-center gap-2 ${
                  !activeCategoryCode
                    ? "bg-blue-50 text-[#0D4D4D]"
                    : "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]"
                }`}
              >
                {!activeCategoryCode && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[#0D4D4D] rounded-r-full" />
                )}
                <SlidersHorizontal className="h-4 w-4 text-[#0D4D4D]" />
                {t("allCategories")}
              </button>
            </li>
            {loadingCategories ? (
              <li className="px-3 py-2 text-xs text-gray-400">{t("loadError")}...</li>
            ) : (
              categoryTree.map((cat) => (
                <li key={cat.code} className="relative">
                  <button
                    onClick={() => handleCategoryClick(cat.code)}
                    onMouseEnter={() => setHoveredLevel1(cat.code)}
                    className={`w-full rounded-lg px-3 py-2 text-left transition-all relative group ${
                      hoveredLevel1 === cat.code
                        ? "bg-blue-50 text-[#0D4D4D]"
                        : categoryButtonClass(cat)
                    }`}
                  >
                    {(activeCategoryCode === cat.code ||
                      hoveredLevel1 === cat.code ||
                      (activeCategoryCode && categoryContainsCode(cat, activeCategoryCode))) && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[#0D4D4D] rounded-r-full" />
                    )}
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold">{cat.name}</span>
                      {(cat.children?.length || 0) > 0 && (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-current" />
                      )}
                    </span>
                    {(cat.children?.length || 0) > 0 && (
                      <span className="mt-0.5 block truncate text-[11px] font-normal text-gray-400 group-hover:text-[#0D4D4D]/70">
                        {cat.children
                          ?.slice(0, 2)
                          .map((child) => child.name)
                          .join(" / ")}
                      </span>
                    )}
                  </button>

                  {/* 二级飞出面板 — 相对当前 hover 品类项定位 */}
                  {hoveredLevel1 === cat.code &&
                    (cat.children?.length || 0) > 0 && (
                      <div className="absolute left-full top-0 z-30 w-[600px] max-w-[calc(100vw-20rem)] rounded-xl border border-gray-100 bg-white p-5 shadow-xl">
                        <div className="max-h-[480px] overflow-y-auto pr-2 space-y-5">
                          {cat.children?.map((level2) => (
                            <div
                              key={level2.code}
                              className="border-b border-dashed border-gray-100 pb-4 last:border-b-0 last:pb-0"
                            >
                              <button
                                onClick={() => handleCategoryClick(level2.code)}
                                className={`mb-2 block text-left text-sm font-bold leading-6 transition-colors ${
                                  activeCategoryCode && categoryContainsCode(level2, activeCategoryCode)
                                    ? "text-[#0D4D4D]"
                                    : "text-gray-900 hover:text-[#0D4D4D]"
                                }`}
                              >
                                {level2.name}
                              </button>
                              <div className="flex flex-wrap gap-x-4 gap-y-2">
                                {(level2.children || []).map((level3) => (
                                  <button
                                    key={level3.code}
                                    onClick={() => handleCategoryClick(level3.code)}
                                    className={`text-left text-sm leading-6 transition-colors ${
                                      activeCategoryCode === level3.code
                                        ? "font-semibold text-[#0D4D4D]"
                                        : "text-gray-600 hover:text-[#0D4D4D]"
                                    }`}
                                  >
                                    {level3.name}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                </li>
              ))
            )}
          </ul>
        </div>

        {/* Mobile: 折叠版 */}
        <div className="lg:hidden space-y-1">
          <button
            onClick={() => {
              handleCategoryClick("");
              setExpandedLevel1("");
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
              !activeCategoryCode
                ? "bg-blue-50 text-[#0D4D4D] font-semibold"
                : "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]"
            }`}
          >
            <SlidersHorizontal className="h-4 w-4 text-[#0D4D4D]" />
            {t("allCategories")}
          </button>
          {loadingCategories ? (
            <div className="px-3 py-2 text-xs text-gray-400">{t("loadError")}...</div>
          ) : (
            categoryTree.map((cat) => (
              <div key={cat.code}>
                <button
                  onClick={() => handleMobileLevel1Click(cat)}
                  className={`w-full px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between gap-2 ${categoryButtonClass(cat)}`}
                >
                  <span className="min-w-0 text-left">
                    <span className="block font-semibold">{cat.name}</span>
                  </span>
                  {(cat.children?.length || 0) > 0 && (
                    <ChevronRight
                      className={`h-3.5 w-3.5 transition-transform ${
                        expandedLevel1 === cat.code ? "rotate-90" : ""
                      }`}
                    />
                  )}
                </button>
                {expandedLevel1 === cat.code && (
                  <div className="mt-1 space-y-3 border-l border-gray-100 pl-3 ml-3">
                    {cat.children?.map((level2) => (
                      <div key={level2.code} className="space-y-1">
                        <button
                          onClick={() => handleCategoryClick(level2.code, false)}
                          className={`text-left text-sm font-bold transition-colors ${
                            activeCategoryCode && categoryContainsCode(level2, activeCategoryCode)
                              ? "text-[#0D4D4D]"
                              : "text-gray-900 hover:text-[#0D4D4D]"
                          }`}
                        >
                          {level2.name}
                        </button>
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {level2.children?.map((level3) => (
                            <button
                              key={level3.code}
                              onClick={() => handleCategoryClick(level3.code, false)}
                              className={`text-left text-xs transition-colors ${
                                activeCategoryCode === level3.code
                                  ? "font-semibold text-[#0D4D4D]"
                                  : "text-gray-600 hover:text-[#0D4D4D]"
                              }`}
                            >
                              {level3.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Quick Links */}
        {showQuickLinks && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
              Quick Links
            </p>
            <button
              onClick={() => {
                if (onFeaturedToggle) {
                  onFeaturedToggle();
                } else {
                  router.push(`/${locale}/mall?featured=true`);
                }
              }}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                showFeatured
                  ? "bg-orange-50 font-semibold text-[#FF6B35]"
                  : "text-[#0D4D4D] hover:bg-blue-50"
              }`}
            >
              <Star className="h-3.5 w-3.5" />
              {t("featuredProducts")}
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
