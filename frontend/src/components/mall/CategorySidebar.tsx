"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";

function categoryContainsCode(category: CategoryTreeNode, code: string): boolean {
  if (category.code === code) return true;
  return (category.children || []).some((child) => categoryContainsCode(child, code));
}

/** 取品类英文名首字母(用于图标显示) */
function getInitialLetter(name: string): string {
  // 尝试提取英文部分(如 "照明电气 Lighting & Electrical" → L)
  const enMatch = name.match(/[A-Za-z]/);
  if (enMatch) return enMatch[0].toUpperCase();
  // 纯中文取第一个字
  return name[0] || "?";
}

/**
 * 商城左侧品类导航侧栏 — 深青风格 + 首字母圆角图标。
 * 参考 HTML .side-card + .category-list
 */
export function CategorySidebar({
  activeCategoryCode = "",
  showQuickLinks = false,
  showFeatured = false,
  onFeaturedToggle,
}: {
  activeCategoryCode?: string;
  showQuickLinks?: boolean;
  showFeatured?: boolean;
  onFeaturedToggle?: () => void;
}) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const { tree: categoryTree, isLoading: loadingCategories } = useCategoryTree();

  const [hoveredLevel1, setHoveredLevel1] = useState("");

  const handleCategoryClick = (code: string, closeHover = true) => {
    const next = activeCategoryCode === code ? "" : code;
    router.push(`/${locale}/mall${next ? `?cat=${next}` : ""}`, { scroll: false });
    if (closeHover) setHoveredLevel1("");
  };

  return (
    <aside className="w-[240px] shrink-0 hidden lg:block">
      <div
        className="sticky top-[148px] rounded-xl border border-line bg-white p-4"
        style={{ boxShadow: "0 1px 2px rgba(16,36,65,.05), 0 2px 6px rgba(16,36,65,.04)" }}
      >
        {/* 标题 */}
        <div className="pb-2.5 mb-2.5 border-b-2 border-gold">
          <span className="text-teal-900 text-sm font-black">
            {t("categoryNav")}
          </span>
        </div>

        {/* 品类列表 */}
        <div
          className="relative"
          onMouseLeave={() => setHoveredLevel1("")}
        >
          <ul className="space-y-0.5">
            {loadingCategories ? (
              <li className="px-3 py-2 text-xs text-muted">{t("loadError")}...</li>
            ) : (
              categoryTree.map((cat) => {
                const isActive = activeCategoryCode === cat.code ||
                  (activeCategoryCode && categoryContainsCode(cat, activeCategoryCode));
                const isHovered = hoveredLevel1 === cat.code;
                const letter = getInitialLetter(cat.name);

                return (
                  <li key={cat.code} className="relative">
                    <button
                      onClick={() => handleCategoryClick(cat.code)}
                      onMouseEnter={() => setHoveredLevel1(cat.code)}
                      className={`w-full rounded-lg px-2.5 py-2 text-left transition-all grid grid-cols-[30px_1fr_auto] gap-2.5 items-center min-h-[46px] ${
                        isActive || isHovered
                          ? "bg-teal-50 text-teal-900"
                          : "text-ink-2 hover:bg-teal-50 hover:text-teal-900"
                      }`}
                    >
                      {/* 首字母图标 */}
                      <span
                        className={`w-[30px] h-[30px] rounded-[7px] grid place-items-center text-xs font-black transition-colors ${
                          isActive
                            ? "bg-teal-800 text-white"
                            : "text-white"
                        }`}
                        style={
                          isActive
                            ? undefined
                            : { background: "linear-gradient(135deg, #07808b, #00505a, #003f46)" }
                        }
                      >
                        {letter}
                      </span>

                      {/* 品类名 */}
                      <span className="min-w-0">
                        <span className="block text-[13px] font-extrabold leading-tight truncate">
                          {cat.name}
                        </span>
                        {cat.children && cat.children.length > 0 && (
                          <span className="block text-[11px] text-muted mt-0.5 truncate">
                            {cat.children.slice(0, 2).map((c) => c.name).join(" / ")}
                          </span>
                        )}
                      </span>

                      {/* 箭头 */}
                      {(cat.children?.length || 0) > 0 && (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-current" />
                      )}
                    </button>

                    {/* 二级飞出面板 */}
                    {isHovered && (cat.children?.length || 0) > 0 && (
                      <div
                        className="absolute left-full top-0 z-30 w-[600px] max-w-[calc(100vw-20rem)] rounded-xl border border-line bg-white p-5"
                        style={{ boxShadow: "0 8px 20px rgba(16,36,65,.08), 0 28px 60px rgba(16,36,65,.12)" }}
                      >
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
                                    ? "text-teal-900"
                                    : "text-navy hover:text-teal-900"
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
                                        ? "font-semibold text-teal-900"
                                        : "text-muted hover:text-teal-900"
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
                );
              })
            )}
          </ul>
        </div>

        {/* 底部 CTA */}
        <div
          className="mt-3.5 p-4 rounded-xl text-white"
          style={{ background: "linear-gradient(135deg, #006773, #07808b)" }}
        >
          <strong className="block text-sm mb-1">{t("quickSourcing")}</strong>
          <p className="text-[12.5px] text-[#bfe1e0] mb-3">{t("quickSourcingHint")}</p>
          <button
            onClick={() => {
              if (onFeaturedToggle) onFeaturedToggle();
              else router.push(`/${locale}/mall?featured=true`);
            }}
            className="w-full h-10 rounded-[10px] bg-gold text-white font-extrabold text-sm hover:bg-white hover:text-teal-900 transition-colors"
          >
            {t("requestQuote")}
          </button>
        </div>
      </div>
    </aside>
  );
}
