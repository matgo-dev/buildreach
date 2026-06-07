"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ChevronRight, SlidersHorizontal, Star, Sparkles } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { listProducts, type ProductListParams, type ProductListResponse } from "@/lib/api/products";
import { ProductGrid } from "@/components/mall/ProductGrid";
import { FilterBar } from "@/components/mall/FilterBar";
import { Pagination } from "@/components/mall/Pagination";
import { RightSidebar } from "@/components/mall/RightSidebar";

const PAGE_SIZE = 20;

function categoryContainsCode(category: CategoryTreeNode, code: string): boolean {
  if (category.code === code) return true;
  return (category.children || []).some((child) => categoryContainsCode(child, code));
}

function MallContent() {
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");

  // URL 参数读取
  const urlCat = searchParams.get("cat") || "";
  const urlKeyword = searchParams.get("keyword") || "";
  const urlSort = searchParams.get("sort") || "newest";
  const urlFeatured = searchParams.get("featured") === "true";
  const urlPage = Number(searchParams.get("page")) || 1;

  // 品类树
  const { tree: categoryTree, isLoading: loadingCategories } = useCategoryTree();

  // 侧栏交互态
  const [hoveredLevel1, setHoveredLevel1] = useState("");
  const [expandedLevel1, setExpandedLevel1] = useState("");

  // 更新 URL 参数的统一方法
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      // 非翻页操作时重置到第 1 页
      if (!("page" in updates)) params.delete("page");
      const qs = params.toString();
      router.replace(`/${locale}/mall${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, locale]
  );

  // SWR 请求商品列表
  const apiParams: ProductListParams = useMemo(
    () => ({
      category_code: urlCat || undefined,
      keyword: urlKeyword || undefined,
      sort: urlSort as ProductListParams["sort"],
      featured: urlFeatured || undefined,
      page: urlPage,
      size: PAGE_SIZE,
    }),
    [urlCat, urlKeyword, urlSort, urlFeatured, urlPage]
  );

  const swrKey = useMemo(
    () => `/api/v1/products?${JSON.stringify(apiParams)}&locale=${locale}`,
    [apiParams, locale]
  );

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR<ProductListResponse>(swrKey, () => listProducts(apiParams), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });

  const products = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 0;

  // 品类选择
  const handleCategoryClick = (code: string, closeHover = true) => {
    const next = urlCat === code ? "" : code;
    updateParams({ cat: next || undefined });
    if (closeHover) setHoveredLevel1("");
  };

  const handleMobileLevel1Click = (category: CategoryTreeNode) => {
    handleCategoryClick(category.code, false);
    setExpandedLevel1((prev) => (prev === category.code ? "" : category.code));
  };

  // 筛选
  const hasActiveFilters = !!(urlCat || urlKeyword || urlFeatured || urlSort !== "newest");
  const clearAll = () => {
    router.replace(`/${locale}/mall`, { scroll: false });
  };

  // 翻页滚动到顶
  const handlePageChange = (page: number) => {
    updateParams({ page: page > 1 ? String(page) : undefined });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const categoryButtonClass = (category: CategoryTreeNode) => {
    const inSelectedPath = urlCat && categoryContainsCode(category, urlCat);
    if (urlCat === category.code || inSelectedPath) {
      return "bg-blue-50 text-[#0D4D4D] font-semibold";
    }
    return "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]";
  };

  const activeLevel1Category = useMemo(
    () => categoryTree.find((c) => c.code === hoveredLevel1) || null,
    [categoryTree, hoveredLevel1]
  );

  return (
    <PublicLayout>
      <div className="flex flex-col lg:flex-row gap-5">
        {/* ===== 左侧品类导航 ===== */}
        <aside className="lg:w-52 shrink-0">
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800">
              <SlidersHorizontal className="h-4 w-4 text-[#0D4D4D]" />
              {t("categoryNav")}
            </h3>

            {/* Desktop: hover 飞出二级面板 */}
            <div
              className="relative hidden lg:block"
              onMouseLeave={() => setHoveredLevel1("")}
            >
              <ul className="space-y-1">
                <li>
                  <button
                    onClick={() => handleCategoryClick("")}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm font-semibold transition-all relative ${
                      !urlCat
                        ? "bg-blue-50 text-[#0D4D4D]"
                        : "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]"
                    }`}
                  >
                    {!urlCat && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[#0D4D4D] rounded-r-full" />
                    )}
                    {t("allCategories")}
                  </button>
                </li>
                {loadingCategories ? (
                  <li className="px-3 py-2 text-xs text-gray-400">{t("loadError")}...</li>
                ) : (
                  categoryTree.map((cat) => (
                    <li key={cat.code}>
                      <button
                        onClick={() => handleCategoryClick(cat.code)}
                        onMouseEnter={() => setHoveredLevel1(cat.code)}
                        className={`w-full rounded-lg px-3 py-2 text-left transition-all relative group ${
                          hoveredLevel1 === cat.code
                            ? "bg-blue-50 text-[#0D4D4D]"
                            : categoryButtonClass(cat)
                        }`}
                      >
                        {(urlCat === cat.code ||
                          hoveredLevel1 === cat.code ||
                          (urlCat && categoryContainsCode(cat, urlCat))) && (
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
                    </li>
                  ))
                )}
              </ul>

              {/* 二级飞出面板 */}
              {activeLevel1Category &&
                (activeLevel1Category.children?.length || 0) > 0 && (
                  <div className="absolute left-full top-0 z-30 w-[600px] max-w-[calc(100vw-20rem)] rounded-xl border border-gray-100 bg-white p-5 shadow-xl">
                    <div className="max-h-[480px] overflow-y-auto pr-2 space-y-5">
                      {activeLevel1Category.children?.map((level2) => (
                        <div
                          key={level2.code}
                          className="border-b border-dashed border-gray-100 pb-4 last:border-b-0 last:pb-0"
                        >
                          <button
                            onClick={() => handleCategoryClick(level2.code)}
                            className={`mb-2 block text-left text-sm font-bold leading-6 transition-colors ${
                              urlCat && categoryContainsCode(level2, urlCat)
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
                                  urlCat === level3.code
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
            </div>

            {/* Mobile: 折叠版 */}
            <div className="lg:hidden space-y-1">
              <button
                onClick={() => {
                  handleCategoryClick("");
                  setExpandedLevel1("");
                }}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  !urlCat
                    ? "bg-blue-50 text-[#0D4D4D] font-semibold"
                    : "text-gray-700 hover:bg-blue-50 hover:text-[#0D4D4D]"
                }`}
              >
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
                                urlCat && categoryContainsCode(level2, urlCat)
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
                                    urlCat === level3.code
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
            <div className="mt-4 border-t border-gray-100 pt-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                Quick Links
              </p>
              <button
                onClick={() => updateParams({ featured: urlFeatured ? undefined : "true", cat: undefined })}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                  urlFeatured
                    ? "bg-orange-50 font-semibold text-[#FF6B35]"
                    : "text-[#0D4D4D] hover:bg-blue-50"
                }`}
              >
                <Star className="h-3.5 w-3.5" />
                {t("featuredProducts")}
              </button>
            </div>
          </div>
        </aside>

        {/* ===== 主内容区 ===== */}
        <div className="flex-1 min-w-0 space-y-3">
          <FilterBar
            keyword={urlKeyword}
            sort={urlSort}
            featured={urlFeatured}
            total={total}
            onKeywordChange={(kw) => updateParams({ keyword: kw || undefined })}
            onSortChange={(s) => updateParams({ sort: s !== "newest" ? s : undefined })}
            onFeaturedToggle={() => updateParams({ featured: urlFeatured ? undefined : "true" })}
            onClearAll={clearAll}
            hasActiveFilters={hasActiveFilters}
          />

          <ProductGrid
            products={products}
            categoryTree={categoryTree}
            isLoading={isLoading}
            error={error}
            onRetry={() => mutate()}
            onClearFilters={clearAll}
          />

          {pages > 1 && (
            <Pagination
              page={urlPage}
              pages={pages}
              total={total}
              size={PAGE_SIZE}
              onPageChange={handlePageChange}
            />
          )}
        </div>

        {/* ===== 右侧栏 ===== */}
        <aside className="hidden xl:block xl:w-48 shrink-0">
          <RightSidebar />
        </aside>
      </div>
    </PublicLayout>
  );
}

export default function MallPage() {
  return (
    <RouteGuard allowRoles={["BUYER", "OPERATOR"]}>
      <Suspense fallback={null}>
        <MallContent />
      </Suspense>
    </RouteGuard>
  );
}
