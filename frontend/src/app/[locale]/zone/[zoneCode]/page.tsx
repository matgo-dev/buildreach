"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Search, X } from "lucide-react";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
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

  const urlCat = searchParams.get("cat") || "";
  const urlKeyword = searchParams.get("keyword") || "";
  const urlSpec = searchParams.get("spec") || "";
  const urlPage = parseInt(searchParams.get("page") || "1", 10) || 1;
  const [specInput, setSpecInput] = useState(urlSpec);

  useEffect(() => {
    setSpecInput(urlSpec);
  }, [urlSpec]);

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

  const handleSpecSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      updateParams({ spec: specInput.trim() || undefined, page: undefined });
    },
    [specInput, updateParams]
  );

  const clearSpec = useCallback(() => {
    setSpecInput("");
    updateParams({ spec: undefined, page: undefined });
  }, [updateParams]);

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
    `/api/v1/zones/${zoneCode}/products?cat=${urlCat}&keyword=${urlKeyword}&spec=${urlSpec}&page=${urlPage}&locale=${locale}`,
    () =>
      zonesApi.products(zoneCode, {
        zone_category_code: urlCat || undefined,
        keyword: urlKeyword || undefined,
        spec: urlSpec || undefined,
        page: urlPage,
        size: PAGE_SIZE,
      }),
    { revalidateOnFocus: false }
  );

  const clearAll = () => updateParams({ cat: undefined, keyword: undefined, spec: undefined, page: undefined });

  const productHref = useMemo(
    () => (productId: number) => `/zone/${zoneCode}/products/${productId}`,
    [zoneCode]
  );

  return (
    <PublicLayout>
      <div className="space-y-4">
        {/* 大类导航 */}
        {!categoriesLoading && categories && categories.length > 0 && (
          <ZoneCategoryNav
            categories={categories}
            activeCode={urlCat}
            allLabel={t("allCategories")}
            onSelect={handleCategorySelect}
          />
        )}

        <form
          onSubmit={handleSpecSubmit}
          className="flex flex-col gap-3 rounded-xl border border-line bg-white px-3 py-3 sm:flex-row sm:items-center"
        >
          <label className="shrink-0 text-sm font-semibold text-slate-700">
            {t("specFilter")}
          </label>
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={specInput}
              onChange={(e) => setSpecInput(e.target.value)}
              placeholder={t("specFilterPlaceholder")}
              className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-9 pr-9 text-sm text-slate-700 outline-none transition-colors focus:border-teal-700 focus:bg-white"
            />
            {specInput && (
              <button
                type="button"
                onClick={clearSpec}
                className="absolute right-2 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-full text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600"
                aria-label={t("clearSpecFilter")}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="h-9 rounded-md bg-teal-800 px-4 text-sm font-semibold text-white transition-colors hover:bg-teal-900"
          >
            {t("applyFilter")}
          </button>
          {(urlKeyword || urlSpec) && (
            <button
              type="button"
              onClick={() => updateParams({ keyword: undefined, spec: undefined, page: undefined })}
              className="h-9 rounded-md px-3 text-sm font-semibold text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              {t("clearSearch")}
            </button>
          )}
        </form>

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
