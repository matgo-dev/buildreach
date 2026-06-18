"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { listProducts, listCertificationOptions, type ProductListParams, type ProductListResponse } from "@/lib/api/products";
import { ProductGrid } from "@/components/mall/ProductGrid";
import { FilterBar } from "@/components/mall/FilterBar";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { RecentViews } from "@/components/mall/RecentViews";
import { RightSidebar } from "@/components/mall/RightSidebar";
import { useAuthStore } from "@/stores/authStore";
import { getBrowsePreferences } from "@/lib/api/buyerPrefs";
import { Loader2 } from "lucide-react";

const PAGE_SIZE = 20;

function MallContent() {
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("mall");

  const { tree: categoryTree } = useCategoryTree();

  // 买方浏览偏好：仅 BUYER 角色才拉取
  const isBuyer = useAuthStore((s) => s.hasRole("BUYER"));
  const { data: prefCodes } = useSWR<string[]>(
    isBuyer ? "buyer-browse-prefs" : null,
    () => getBrowsePreferences(),
    { revalidateOnFocus: false },
  );

  // 认证筛选选项
  const { data: certOptions } = useSWR<string[]>(
    "product-certification-options",
    () => listCertificationOptions(),
    { revalidateOnFocus: false },
  );

  // 品类侧栏展开状态
  const [showAllCategories, setShowAllCategories] = useState(false);

  // URL 参数读取
  const urlCat = searchParams.get("cat") || "";
  const urlKeyword = searchParams.get("keyword") || "";
  const urlSort = searchParams.get("sort") || "newest";
  const urlFeatured = searchParams.get("featured") === "true";
  const urlSupplyMode = searchParams.get("supply_mode") || "";
  const urlCertification = searchParams.get("certification") || "";

  // 更新 URL 参数的统一方法
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      // 无限滚动不再需要 page 参数
      params.delete("page");
      const qs = params.toString();
      router.replace(`/${locale}/mall${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, locale]
  );

  // 无限滚动状态
  const [allProducts, setAllProducts] = useState<ProductListResponse["items"]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // 筛选条件变化时的 fingerprint，用于检测重置
  const filterFingerprint = useMemo(
    () => JSON.stringify({ urlCat, urlKeyword, urlSort, urlFeatured, urlSupplyMode, urlCertification, prefCodes, showAllCategories }),
    [urlCat, urlKeyword, urlSort, urlFeatured, urlSupplyMode, urlCertification, prefCodes, showAllCategories]
  );

  // 首页请求参数（page=1）
  const apiParams: ProductListParams = useMemo(
    () => ({
      category_code: urlCat || undefined,
      keyword: urlKeyword || undefined,
      sort: urlSort as ProductListParams["sort"],
      featured: urlFeatured || undefined,
      supply_mode: urlSupplyMode || undefined,
      certification: urlCertification || undefined,
      page: 1,
      size: PAGE_SIZE,
      ...(prefCodes && prefCodes.length > 0 && !urlCat
        ? { all_categories: showAllCategories || undefined }
        : {}),
    }),
    [urlCat, urlKeyword, urlSort, urlFeatured, urlSupplyMode, urlCertification, prefCodes, showAllCategories]
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

  // 筛选条件变化 → 重置累积数据
  // 用 swrKey 而非 filterFingerprint：prefCodes 加载不改变 API 请求，
  // 但会改变 fingerprint 导致 allProducts 被清空而 SWR 不重新请求 → 空白页
  useEffect(() => {
    setAllProducts([]);
    setCurrentPage(1);
    setTotalCount(0);
    setTotalPages(0);
  }, [swrKey]);

  // 首页数据到达 → 初始化
  useEffect(() => {
    if (data) {
      setAllProducts(data.items);
      setCurrentPage(data.page);
      setTotalCount(data.total);
      setTotalPages(data.pages);
    }
  }, [data]);

  // 加载更多
  const loadMore = useCallback(async () => {
    if (isLoadingMore || currentPage >= totalPages) return;
    setIsLoadingMore(true);
    try {
      const nextPage = currentPage + 1;
      const res = await listProducts({ ...apiParams, page: nextPage });
      setAllProducts((prev) => [...prev, ...res.items]);
      setCurrentPage(nextPage);
      setTotalCount(res.total);
      setTotalPages(res.pages);
    } catch {
      // 加载失败静默，用户可继续滚动重试
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, currentPage, totalPages, apiParams]);

  // IntersectionObserver 触底加载
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const hasMore = currentPage < totalPages;

  const hasActiveFilters = !!(urlCat || urlKeyword || urlFeatured || urlSupplyMode || urlCertification || urlSort !== "newest");
  const clearAll = () => {
    router.replace(`/${locale}/mall`, { scroll: false });
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
          prefCodes={urlCat ? undefined : prefCodes}
          showAllCategories={showAllCategories || !!urlCat}
          onToggleAllCategories={() => setShowAllCategories((v) => !v)}
        />

        {/* 主内容区 */}
        <div className="min-w-0 space-y-4">
          {/* 最近浏览 */}
          {isBuyer && <RecentViews />}

          <FilterBar
            keyword={urlKeyword}
            sort={urlSort}
            featured={urlFeatured}
            supplyMode={urlSupplyMode}
            certification={urlCertification}
            certificationOptions={certOptions ?? []}
            total={totalCount}
            activeCategoryCode={urlCat}
            categoryTree={categoryTree}
            onKeywordChange={(kw) => updateParams({ keyword: kw || undefined })}
            onSortChange={(s) => updateParams({ sort: s !== "newest" ? s : undefined })}
            onFeaturedToggle={() => updateParams({ featured: urlFeatured ? undefined : "true" })}
            onSupplyModeChange={(mode) => updateParams({ supply_mode: mode || undefined })}
            onCertificationChange={(cert) => updateParams({ certification: cert || undefined })}
            onCategoryChange={(code) => updateParams({ cat: code || undefined })}
            onClearAll={clearAll}
            hasActiveFilters={hasActiveFilters}
          />

          <ProductGrid
            products={allProducts}
            categoryTree={categoryTree}
            isLoading={isLoading && allProducts.length === 0}
            error={error}
            onRetry={() => mutate()}
            onClearFilters={clearAll}
          />

          {/* 触底哨兵 + 加载状态 */}
          {hasMore && (
            <div ref={sentinelRef} className="flex items-center justify-center py-6">
              {isLoadingMore && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{t("loadingMore")}</span>
                </div>
              )}
            </div>
          )}

          {/* 全部加载完毕提示 */}
          {!hasMore && allProducts.length > PAGE_SIZE && (
            <div className="py-4 text-center text-xs text-gray-400">
              {t("noMoreProducts")}
            </div>
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
