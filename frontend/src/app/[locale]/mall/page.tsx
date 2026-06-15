"use client";

import React, { Suspense, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { listProducts, type ProductListParams, type ProductListResponse } from "@/lib/api/products";
import { ProductGrid } from "@/components/mall/ProductGrid";
import { FilterBar } from "@/components/mall/FilterBar";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { Pagination } from "@/components/mall/Pagination";
import { RightSidebar } from "@/components/mall/RightSidebar";

const PAGE_SIZE = 20;

function MallContent() {
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");

  const { tree: categoryTree } = useCategoryTree();

  // URL 参数读取
  const urlCat = searchParams.get("cat") || "";
  const urlKeyword = searchParams.get("keyword") || "";
  const urlSort = searchParams.get("sort") || "newest";
  const urlFeatured = searchParams.get("featured") === "true";
  const urlSupplyMode = searchParams.get("supply_mode") || "";
  const urlPage = Number(searchParams.get("page")) || 1;

  // 更新 URL 参数的统一方法
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
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
      supply_mode: urlSupplyMode || undefined,
      page: urlPage,
      size: PAGE_SIZE,
    }),
    [urlCat, urlKeyword, urlSort, urlFeatured, urlSupplyMode, urlPage]
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

  const hasActiveFilters = !!(urlCat || urlKeyword || urlFeatured || urlSupplyMode || urlSort !== "newest");
  const clearAll = () => {
    router.replace(`/${locale}/mall`, { scroll: false });
  };

  const handlePageChange = (page: number) => {
    updateParams({ page: page > 1 ? String(page) : undefined });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <PublicLayout>
      {/* 三栏布局:左品类(240) + 中内容(auto) + 右客服/RFQ(300) */}
      <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_300px] gap-5">
        {/* 左侧品类导航 */}
        <CategorySidebar
          activeCategoryCode={urlCat}
          showQuickLinks
          showFeatured={urlFeatured}
          onFeaturedToggle={() => updateParams({ featured: urlFeatured ? undefined : "true" })}
        />

        {/* 主内容区 */}
        <div className="min-w-0 space-y-4">
          <FilterBar
            keyword={urlKeyword}
            sort={urlSort}
            featured={urlFeatured}
            supplyMode={urlSupplyMode}
            total={total}
            activeCategoryCode={urlCat}
            categoryTree={categoryTree}
            onKeywordChange={(kw) => updateParams({ keyword: kw || undefined })}
            onSortChange={(s) => updateParams({ sort: s !== "newest" ? s : undefined })}
            onFeaturedToggle={() => updateParams({ featured: urlFeatured ? undefined : "true" })}
            onSupplyModeChange={(mode) => updateParams({ supply_mode: mode || undefined })}
            onCategoryChange={(code) => updateParams({ cat: code || undefined })}
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

        {/* 右侧栏 */}
        <RightSidebar />
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
