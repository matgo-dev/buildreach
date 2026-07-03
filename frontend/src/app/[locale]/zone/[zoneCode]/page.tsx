"use client";

import React, { Suspense, useCallback, useMemo } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ShieldCheck } from "lucide-react";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { useAuthStore } from "@/stores/authStore";
import { zonesApi, type ZoneCategory } from "@/lib/api/zones";
import type { ProductListResponse } from "@/lib/api/products";
import { ZoneCategoryNav } from "@/components/zone/ZoneCategoryNav";
import { ProductGrid } from "@/components/mall/ProductGrid";
import { Pagination } from "@/components/mall/Pagination";

const PAGE_SIZE = 20;

function ZoneContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("zone");
  const zoneCode = String(params.zoneCode);

  const { tree: categoryTree } = useCategoryTree();
  const zoneInfo = useAuthStore((s) => s.user?.zones.find((z) => z.code === zoneCode));
  const zoneName = zoneInfo ? (locale === "zh" ? zoneInfo.name_zh : zoneInfo.name_en || zoneInfo.name_zh) : zoneCode;

  const urlCat = searchParams.get("cat") || "";
  const urlPage = parseInt(searchParams.get("page") || "1", 10) || 1;

  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const p = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) p.set(key, value);
        else p.delete(key);
      }
      const qs = p.toString();
      router.replace(`/${locale}/zone/${zoneCode}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, locale, zoneCode]
  );

  const handleCategorySelect = useCallback(
    (code: string) => {
      updateParams({ cat: code || undefined, page: undefined });
    },
    [updateParams]
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      updateParams({ page: newPage > 1 ? String(newPage) : undefined });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [updateParams]
  );

  const {
    data: categories,
    isLoading: categoriesLoading,
  } = useSWR<ZoneCategory[]>(
    `/api/v1/zones/${zoneCode}/categories?locale=${locale}`,
    () => zonesApi.categories(zoneCode),
    { revalidateOnFocus: false }
  );

  const {
    data: productData,
    error: productError,
    isLoading: productsLoading,
    mutate: refetchProducts,
  } = useSWR<ProductListResponse>(
    `/api/v1/zones/${zoneCode}/products?cat=${urlCat}&page=${urlPage}&locale=${locale}`,
    () =>
      zonesApi.products(zoneCode, {
        zone_category_code: urlCat || undefined,
        page: urlPage,
        size: PAGE_SIZE,
      }),
    { revalidateOnFocus: false }
  );

  const clearAll = () => updateParams({ cat: undefined, page: undefined });

  const productHref = useMemo(
    () => (productId: number) => `/zone/${zoneCode}/products/${productId}`,
    [zoneCode]
  );

  return (
    <PublicLayout>
      <div className="space-y-4">
        {/* 专区标题条 */}
        <div className="flex items-center gap-2.5 rounded-xl border border-teal-800/15 bg-gradient-to-r from-[#00505a] to-[#003d45] px-5 py-4 text-white">
          <ShieldCheck className="h-6 w-6 shrink-0" />
          <div>
            <h1 className="text-lg font-bold">{zoneName}</h1>
            <p className="text-xs text-white/70">{t("landingSubtitle")}</p>
          </div>
        </div>

        {/* 大类导航 */}
        {!categoriesLoading && categories && categories.length > 0 && (
          <ZoneCategoryNav
            categories={categories}
            activeCode={urlCat}
            allLabel={t("allCategories")}
            onSelect={handleCategorySelect}
          />
        )}

        {/* 商品网格 */}
        <ProductGrid
          products={productData?.items ?? []}
          categoryTree={categoryTree}
          isLoading={productsLoading}
          error={productError}
          onRetry={() => refetchProducts()}
          onClearFilters={clearAll}
          productHref={productHref}
        />

        {productData && productData.pages > 1 && (
          <Pagination
            page={productData.page}
            pages={productData.pages}
            total={productData.total}
            size={productData.size}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </PublicLayout>
  );
}

function ZoneContentGated() {
  const params = useParams();
  const zoneCode = String(params.zoneCode);
  return (
    <RouteGuard requireZone={zoneCode}>
      <ZoneContent />
    </RouteGuard>
  );
}

export default function ZonePage() {
  return (
    <Suspense fallback={null}>
      <ZoneContentGated />
    </Suspense>
  );
}
