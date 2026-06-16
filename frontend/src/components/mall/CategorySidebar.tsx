"use client";

import { useRef, useState, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { LetterIcon } from "./LetterIcon";
import { MallButton } from "./MallButton";

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
 *
 * prefCodes: 买方的经营品类偏好 codes，有值时默认只显示这些 L1 品类
 * showAllCategories: 是否展开显示全部品类
 * onToggleAllCategories: 切换展开/收起
 */
export function CategorySidebar({
  activeCategoryCode = "",
  showQuickLinks = false,
  showFeatured = false,
  onFeaturedToggle,
  prefCodes,
  showAllCategories = false,
  onToggleAllCategories,
}: {
  activeCategoryCode?: string;
  showQuickLinks?: boolean;
  showFeatured?: boolean;
  onFeaturedToggle?: () => void;
  prefCodes?: string[];
  showAllCategories?: boolean;
  onToggleAllCategories?: () => void;
}) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const { tree: categoryTree, isLoading: loadingCategories } = useCategoryTree();

  const [hoveredLevel1, setHoveredLevel1] = useState("");
  const [flyoutTop, setFlyoutTop] = useState(0);
  const asideRef = useRef<HTMLElement>(null);
  const hoveredCategory = categoryTree.find((cat) => cat.code === hoveredLevel1);

  // 当有偏好且未展开全部时，只显示偏好品类
  const hasPref = !!prefCodes && prefCodes.length > 0;
  const filteredTree =
    hasPref && !showAllCategories
      ? categoryTree.filter((cat) => prefCodes!.includes(cat.code))
      : categoryTree;

  const handleCategoryClick = (code: string, closeHover = true) => {
    const next = activeCategoryCode === code ? "" : code;
    router.push(`/${locale}/mall${next ? `?cat=${next}` : ""}`, { scroll: false });
    if (closeHover) setHoveredLevel1("");
  };

  const handleAllCategoriesClick = () => {
    router.push(`/${locale}/mall`, { scroll: false });
    setHoveredLevel1("");
  };

  const handleLevel1MouseEnter = (
    code: string,
    event: MouseEvent<HTMLButtonElement>,
  ) => {
    setHoveredLevel1(code);
    const asideTop = asideRef.current?.getBoundingClientRect().top ?? 0;
    const buttonTop = event.currentTarget.getBoundingClientRect().top - asideTop;
    const maxTop = Math.max(0, window.innerHeight - asideTop - 500);
    setFlyoutTop(Math.min(Math.max(buttonTop, 0), maxTop));
  };

  return (
    <aside
      ref={asideRef}
      className="sticky top-[148px] z-30 hidden w-[240px] shrink-0 self-start lg:block"
      onMouseLeave={() => setHoveredLevel1("")}
    >
      <div
        className="rounded-xl border border-line bg-white p-4"
        style={{
          maxHeight: "calc(100vh - 164px)",
          overflowY: "auto",
          boxShadow: "0 1px 2px rgba(16,36,65,.05), 0 2px 6px rgba(16,36,65,.04)",
        }}
      >
        {/* 标题 */}
        <div className="pb-2.5 mb-2.5 border-b-2 border-gold">
          <span className="text-teal-900 text-sm font-black">
            {t("categoryNav")}
          </span>
        </div>

        {/* 品类列表 */}
        <div className="relative">
          <ul className="space-y-0.5">
            <li>
              <button
                onClick={handleAllCategoriesClick}
                onMouseEnter={() => setHoveredLevel1("")}
                className={`w-full rounded-lg px-2.5 py-2 text-left transition-all grid grid-cols-[30px_1fr_auto] gap-2.5 items-center min-h-[46px] ${
                  !activeCategoryCode
                    ? "bg-teal-50 text-teal-900"
                    : "text-ink-2 hover:bg-teal-50 hover:text-teal-900"
                }`}
              >
                <LetterIcon letter={t("allCategories").slice(0, 1)} active={!activeCategoryCode} />
                <span className="min-w-0">
                  <span className="block text-[13px] font-extrabold leading-tight truncate">
                    {t("allCategories")}
                  </span>
                </span>
              </button>
            </li>
            {loadingCategories ? (
              <li className="px-3 py-2 text-xs text-muted">{t("loadError")}...</li>
            ) : (
              filteredTree.map((cat) => {
                const isActive = activeCategoryCode === cat.code ||
                  (activeCategoryCode && categoryContainsCode(cat, activeCategoryCode));
                const isHovered = hoveredLevel1 === cat.code;
                const letter = getInitialLetter(cat.name);
                // 展开全部时，对偏好品类加小圆点标记
                const isPref = hasPref && showAllCategories && prefCodes!.includes(cat.code);

                return (
                  <li key={cat.code} className="relative">
                    <button
                      onClick={() => handleCategoryClick(cat.code)}
                      onMouseEnter={(event) => handleLevel1MouseEnter(cat.code, event)}
                      className={`w-full rounded-lg px-2.5 py-2 text-left transition-all grid grid-cols-[30px_1fr_auto] gap-2.5 items-center min-h-[46px] ${
                        isActive || isHovered
                          ? "bg-teal-50 text-teal-900"
                          : "text-ink-2 hover:bg-teal-50 hover:text-teal-900"
                      }`}
                    >
                      {/* 首字母图标 */}
                      <LetterIcon letter={letter} active={!!isActive} />

                      {/* 品类名 */}
                      <span className="min-w-0 relative">
                        <span className="block text-[13px] font-extrabold leading-tight truncate">
                          {cat.name}
                          {/* 偏好品类小圆点标记 */}
                          {isPref && (
                            <span
                              className="inline-block ml-1.5 w-1.5 h-1.5 rounded-full bg-teal-500 align-middle"
                              title={t("myCategories")}
                            />
                          )}
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

                  </li>
                );
              })
            )}
          </ul>
        </div>

        {/* 偏好品类筛选提示 + 展开/收起切换链接 */}
        {hasPref && onToggleAllCategories && (
          <div className="mt-2 px-1">
            {!showAllCategories ? (
              // 当前只显示偏好品类 — 提示 + "查看全部品类"链接
              <div className="text-center">
                <span className="block text-[11px] text-muted mb-1">
                  {t("prefFilterActive", { count: prefCodes!.length })}
                </span>
                <button
                  onClick={onToggleAllCategories}
                  className="text-[12px] text-teal-600 hover:text-teal-800 hover:underline transition-colors"
                >
                  {t("viewAllCategories")}
                </button>
              </div>
            ) : (
              // 当前显示全部 — "仅看我的品类"折叠链接
              <div className="text-center">
                <button
                  onClick={onToggleAllCategories}
                  className="text-[12px] text-teal-600 hover:text-teal-800 hover:underline transition-colors"
                >
                  {t("myCategories")}
                </button>
              </div>
            )}
          </div>
        )}

        {/* 底部 CTA */}
        <div
          className="mt-3.5 p-4 rounded-xl text-white"
          style={{ background: "linear-gradient(135deg, #006773, #07808b)" }}
        >
          <strong className="block text-sm mb-1">{t("quickSourcing")}</strong>
          <p className="text-[12.5px] text-[#bfe1e0] mb-3">{t("quickSourcingHint")}</p>
          <MallButton
            variant="gold"
            block
            onClick={() => router.push(`/${locale}/buyer/cart`)}
          >
            {t("requestQuote")}
          </MallButton>
        </div>
      </div>

      {/* 二级飞出面板放在滚动卡片外，避免裁剪，同时不影响左侧列表滚动 */}
      {hoveredCategory && (hoveredCategory.children?.length || 0) > 0 && (
        <div
          className="absolute left-full z-40 w-[600px] max-w-[calc(100vw-20rem)] rounded-xl border border-line bg-white p-5"
          style={{
            top: flyoutTop,
            boxShadow: "0 8px 20px rgba(16,36,65,.08), 0 28px 60px rgba(16,36,65,.12)",
          }}
        >
          <div className="max-h-[480px] overflow-y-auto pr-2 space-y-5">
            {hoveredCategory.children?.map((level2) => (
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
    </aside>
  );
}
