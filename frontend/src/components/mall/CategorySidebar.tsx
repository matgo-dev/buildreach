"use client";

import { useRef, useState, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { LayoutGrid } from "lucide-react";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";

// 每行显示的 L1 品类数:中文 4 个,英文/斯瓦希里 3 个(词长)
const CATS_PER_ROW_ZH = 4;
const CATS_PER_ROW_OTHER = 3;
const HOME_MAX_ROWS = 11;

/** 将 L1 品类按 CATS_PER_ROW 分组 */
function chunkArray<T>(arr: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    result.push(arr.slice(i, i + size));
  }
  return result;
}

/** 取品类显示短名: short_name → name 截取(中文2字,英文8字符) */
function getShortName(cat: CategoryTreeNode, locale: string): string {
  if (cat.short_name) return cat.short_name;
  // fallback: 中文取前 2 字,英文/斯瓦希里取前 8 字符
  const limit = locale === "zh" ? 2 : 8;
  const name = cat.name;
  if (name.length <= limit) return name;
  return name.slice(0, limit) + "…";
}

/**
 * 商城左侧品类导航侧栏 — 鑫方盛风格：每行4个短名，hover 展开子品类。
 *
 * variant:
 * - "home" (默认): 首页模式，不 sticky，参与三栏等高
 * - "mall": 商城列表页模式，sticky 定位
 */
export function CategorySidebar({
  activeCategoryCode = "",
  variant = "home",
}: {
  activeCategoryCode?: string;
  variant?: "home" | "mall";
}) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const { tree: categoryTree, isLoading: loadingCategories, error: categoryError } = useCategoryTree();

  const [hoveredRowIdx, setHoveredRowIdx] = useState<number | null>(null);
  const [flyoutTop, setFlyoutTop] = useState(0);
  const asideRef = useRef<HTMLElement>(null);

  // 分组为行:按语言调整每行数量
  const catsPerRow = locale === "zh" ? CATS_PER_ROW_ZH : CATS_PER_ROW_OTHER;
  const rows = chunkArray(categoryTree, catsPerRow);
  const isSticky = variant === "mall";
  const isHome = variant === "home";
  const visibleRows = isHome ? rows.slice(0, HOME_MAX_ROWS) : rows;
  const hasHiddenRows = isHome && rows.length > visibleRows.length;
  const hoveredRow = hoveredRowIdx !== null ? visibleRows[hoveredRowIdx] : null;

  const handleCategoryClick = (code: string) => {
    const next = activeCategoryCode === code ? "" : code;
    router.push(`/${locale}/mall${next ? `?cat=${next}` : ""}`, { scroll: false });
    setHoveredRowIdx(null);
  };

  const handleViewAllCategories = () => {
    router.push(`/${locale}/mall`, { scroll: false });
    setHoveredRowIdx(null);
  };

  const handleRowMouseEnter = (
    rowIdx: number,
    event: MouseEvent<HTMLDivElement>,
  ) => {
    setHoveredRowIdx(rowIdx);
    const asideTop = asideRef.current?.getBoundingClientRect().top ?? 0;
    const rowTop = event.currentTarget.getBoundingClientRect().top - asideTop;
    // flyout 最大高度约 480px，避免超出视口
    const maxTop = Math.max(0, window.innerHeight - asideTop - 500);
    setFlyoutTop(Math.min(Math.max(rowTop, 0), maxTop));
  };

  return (
    <aside
      ref={asideRef}
      className={`relative hidden w-[260px] shrink-0 lg:block ${
        isSticky ? "sticky top-[148px] z-30 self-start" : "self-stretch"
      }`}
      onMouseLeave={() => setHoveredRowIdx(null)}
    >
      <div
        className={`rounded-xl border border-line bg-white flex flex-col ${isSticky ? "" : "h-full"}`}
        style={{
          ...(isSticky
            ? { maxHeight: "calc(100vh - 164px)" }
            : {}),
          boxShadow:
            "0 1px 2px rgba(16,36,65,.05), 0 2px 6px rgba(16,36,65,.04)",
        }}
      >
        {/* 头部 — 固定不滚动 */}
        <div className="flex items-center gap-2 px-4 py-3 rounded-t-xl bg-teal-800 text-white shrink-0">
          <LayoutGrid className="w-4 h-4" />
          <span className="text-sm font-bold">{t("allCategoryNav")}</span>
        </div>

        {/* 品类行列表 — 首页露出稳定快捷入口,列表页保留完整滚动 */}
        <div className={`relative py-1 min-h-0 flex-1 ${isHome ? "flex flex-col overflow-hidden" : "overflow-y-auto"}`}>
          {loadingCategories ? (
            <div className="px-4 py-3 text-xs text-muted">{t("loading")}</div>
          ) : categoryError ? (
            <div className="px-4 py-3 text-xs text-red-500">{t("loadError")}</div>
          ) : (
            visibleRows.map((row, rowIdx) => {
              const isHovered = hoveredRowIdx === rowIdx;
              const hasActiveChild = row.some(
                (cat) =>
                  activeCategoryCode === cat.code ||
                  cat.children?.some(
                    (c2) =>
                      c2.code === activeCategoryCode ||
                      c2.children?.some((c3) => c3.code === activeCategoryCode),
                  ),
              );

              return (
                <div
                  key={rowIdx}
                  onMouseEnter={(e) => handleRowMouseEnter(rowIdx, e)}
                  className={`relative flex items-center px-4 ${isHome ? "flex-1 py-0" : "py-2.5"} cursor-pointer transition-colors ${
                    isHovered || hasActiveChild
                      ? "bg-teal-50"
                      : "hover:bg-gray-50"
                  }`}
                >
                  {/* 左侧竖线指示器 */}
                  {(isHovered || hasActiveChild) && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[60%] rounded-r-full bg-teal-700" />
                  )}

                  {/* 品类短名 */}
                  <div className="flex-1 min-w-0">
                    <span
                      className={`text-[13px] leading-relaxed whitespace-nowrap overflow-hidden text-ellipsis block ${
                        isHovered || hasActiveChild
                          ? "text-teal-800 font-bold"
                          : "text-gray-700"
                      }`}
                    >
                      {row.map((cat, i) => (
                        <span key={cat.code}>
                          {i > 0 && (
                            <span className="mx-1 text-gray-300">/</span>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCategoryClick(cat.code);
                            }}
                            className={`hover:text-teal-900 transition-colors ${
                              activeCategoryCode === cat.code
                                ? "text-teal-900 font-bold"
                                : ""
                            }`}
                          >
                            {getShortName(cat, locale)}
                          </button>
                        </span>
                      ))}
                    </span>
                  </div>

                  {/* 右侧箭头 */}
                  {row.some((cat) => (cat.children?.length || 0) > 0) && (
                    <svg
                      className={`w-3 h-3 shrink-0 transition-colors ${
                        isHovered ? "text-teal-700" : "text-gray-300"
                      }`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  )}
                </div>
              );
            })
          )}
        </div>

        {hasHiddenRows && (
          <button
            type="button"
            onClick={handleViewAllCategories}
            className="flex shrink-0 items-center justify-center gap-1.5 border-t border-gray-100 px-4 py-2.5 text-[12px] font-semibold text-teal-700 transition-colors hover:bg-teal-50 hover:text-teal-900"
          >
            {t("viewAllCategories")}
            <svg
              className="h-3 w-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path d="M5 12h14" />
              <path d="m13 6 6 6-6 6" />
            </svg>
          </button>
        )}

      </div>

      {/* 二级飞出面板 — 展示该行所有 L1 品类的子品类 */}
      {hoveredRow && hoveredRow.some((cat) => (cat.children?.length || 0) > 0) && (
        <div
          className="absolute left-full z-40 w-[600px] max-w-[calc(100vw-20rem)] rounded-xl border border-line bg-white p-5"
          style={{
            top: flyoutTop,
            boxShadow:
              "0 8px 20px rgba(16,36,65,.08), 0 28px 60px rgba(16,36,65,.12)",
          }}
          onMouseEnter={() => {}} // 保持 hover 状态
          onMouseLeave={() => setHoveredRowIdx(null)}
        >
          <div className="max-h-[480px] overflow-y-auto pr-2 space-y-5">
            {hoveredRow.map((l1Cat) => {
              if (!l1Cat.children || l1Cat.children.length === 0) return null;
              return (
                <div key={l1Cat.code}>
                  {/* L1 完整名称作为分组标题 */}
                  <button
                    onClick={() => handleCategoryClick(l1Cat.code)}
                    className="mb-2.5 text-[15px] font-bold text-teal-900 hover:text-teal-700 transition-colors"
                  >
                    {l1Cat.name}
                  </button>

                  <div className="space-y-3">
                    {l1Cat.children.map((l2) => (
                      <div
                        key={l2.code}
                        className="flex items-start gap-3"
                      >
                        {/* L2 品类名 */}
                        <button
                          onClick={() => handleCategoryClick(l2.code)}
                          className={`shrink-0 text-sm font-medium leading-6 transition-colors whitespace-nowrap ${
                            activeCategoryCode === l2.code
                              ? "text-teal-900 font-bold"
                              : "text-gray-600 hover:text-teal-900"
                          }`}
                        >
                          {l2.name}
                        </button>

                        {/* 分隔符 */}
                        {l2.children && l2.children.length > 0 && (
                          <span className="text-gray-300 leading-6 select-none">&gt;</span>
                        )}

                        {/* L3 品类链接 */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          {(l2.children || []).map((l3) => (
                            <button
                              key={l3.code}
                              onClick={() => handleCategoryClick(l3.code)}
                              className={`text-sm leading-6 transition-colors ${
                                activeCategoryCode === l3.code
                                  ? "font-semibold text-teal-900"
                                  : "text-gray-500 hover:text-teal-900"
                              }`}
                            >
                              {l3.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* L1 间分隔线 */}
                  <div className="mt-4 border-b border-dashed border-gray-100 last:border-b-0" />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}
