"use client";

import React, { Suspense, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { Sparkles } from "lucide-react";

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
  const urlPage = Number(searchParams.get("page")) || 1;

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

  return (
    <PublicLayout>
      <div className="flex flex-col lg:flex-row gap-5">
        {/* ===== 左侧品类导航 ===== */}
        <CategorySidebar
          activeCategoryCode={urlCat}
          showQuickLinks
          showFeatured={urlFeatured}
          onFeaturedToggle={() => updateParams({ featured: urlFeatured ? undefined : "true" })}
        />

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
