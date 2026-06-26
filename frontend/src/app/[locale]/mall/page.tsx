"use client";

import React, { Suspense, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { CategoryBreadcrumb } from "@/components/mall/CategoryBreadcrumb";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { listProducts, type ProductListParams, type ProductListResponse } from "@/lib/api/products";
import { ProductGrid } from "@/components/mall/ProductGrid";
import { FilterBar } from "@/components/mall/FilterBar";
import { Pagination } from "@/components/mall/Pagination";
import { RecentViews } from "@/components/mall/RecentViews";
import { useAuthStore } from "@/stores/authStore";

const PAGE_SIZE = 20;

function MallContent() {
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");

  const { tree: categoryTree } = useCategoryTree();
  const isBuyer = useAuthStore((s) => s.hasRole("BUYER"));

  // URL 参数读取；无品类时展示配置的默认品类，避免首屏全是卫浴图片
  const DEFAULT_CATEGORY = process.env.NEXT_PUBLIC_DEFAULT_CATEGORY || "04.014";
  const urlCat = searchParams.get("cat") || DEFAULT_CATEGORY;
  const urlKeyword = searchParams.get("keyword") || "";
  const urlSort = searchParams.get("sort") || "newest";
  const urlFeatured = searchParams.get("featured") === "true";
  const urlSupplyMode = searchParams.get("supply_mode") || "";
  const urlBrand = searchParams.get("brand") || "";
  const urlPage = parseInt(searchParams.get("page") || "1", 10) || 1;

  // 更新 URL 参数的统一方法
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      const qs = params.toString();
      router.replace(`/${locale}/mall${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, locale]
  );

  // 筛选条件变化时重置到第一页
  const updateFilters = useCallback(
    (updates: Record<string, string | undefined>) => {
      updateParams({ ...updates, page: undefined });
    },
    [updateParams]
  );

  // 翻页
  const handlePageChange = useCallback(
    (newPage: number) => {
      updateParams({ page: newPage > 1 ? String(newPage) : undefined });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [updateParams]
  );

  // API 请求参数
  const apiParams: ProductListParams = useMemo(
    () => ({
      category_code: urlCat || undefined,
      keyword: urlKeyword || undefined,
      brand: urlBrand || undefined,
      sort: urlSort as ProductListParams["sort"],
      featured: urlFeatured || undefined,
      supply_mode: urlSupplyMode || undefined,
      page: urlPage,
      size: PAGE_SIZE,
    }),
    [urlCat, urlKeyword, urlBrand, urlSort, urlFeatured, urlSupplyMode, urlPage]
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
  });

  const hasActiveFilters = !!(searchParams.get("cat") || urlKeyword || urlBrand || urlFeatured || urlSupplyMode || urlSort !== "newest");
  const clearAll = () => {
    router.replace(`/${locale}/mall`, { scroll: false });
  };

  return (
    <PublicLayout>
      {/* 全宽单栏布局 */}
      <div className="space-y-4">
        {/* 品类面包屑（有选中品类时显示） */}
        {urlCat && (
          <CategoryBreadcrumb
            categoryCode={urlCat}
            categoryTree={categoryTree}
          />
        )}

        {/* 最近浏览 */}
        {isBuyer && <RecentViews />}

        <FilterBar
          sort={urlSort}
          featured={urlFeatured}
          supplyMode={urlSupplyMode}
          brand={urlBrand}
          total={data?.total ?? 0}
          activeCategoryCode={urlCat}
          categoryTree={categoryTree}
          onSortChange={(s) => updateFilters({ sort: s !== "newest" ? s : undefined })}
          onFeaturedToggle={() => updateFilters({ featured: urlFeatured ? undefined : "true" })}
          onSupplyModeChange={(mode) => updateFilters({ supply_mode: mode || undefined })}
          onCategoryChange={(code) => updateFilters({ cat: code || undefined })}
          onBrandChange={(b) => updateFilters({ brand: b || undefined })}
          onClearAll={clearAll}
          hasActiveFilters={hasActiveFilters}
        />

        <ProductGrid
          products={data?.items ?? []}
          categoryTree={categoryTree}
          isLoading={isLoading}
          error={error}
          onRetry={() => mutate()}
          onClearFilters={clearAll}
        />

        {/* 分页 */}
        {data && data.pages > 1 && (
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            size={data.size}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </PublicLayout>
  );
}

export default function MallPage() {
  return (
    <Suspense fallback={null}>
      <MallContent />
    </Suspense>
  );
}
