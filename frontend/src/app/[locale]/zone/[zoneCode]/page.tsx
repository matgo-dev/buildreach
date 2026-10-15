"use client";

import { Suspense, useCallback, useMemo } from "react";
import { X } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
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

  // 专区卡片不显示平台品类标签:专区有自己的大类轴,平台品类是粗占位(机电/手动工具)或停用的专区专用品类,
  // 公开树里查不到 → 有的卡片有标签有的没有,既不一致也没信息量。
  const noCategoryTree = useMemo(() => [], []);

  const urlCat = searchParams.get("cat") || "";
  const urlScene = searchParams.get("scene") || "";
  const urlKeyword = searchParams.get("keyword") || "";
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

  const handleSceneSelect = useCallback(
    (code: string) => {
      updateParams({ scene: code || undefined, page: undefined });
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
    `/api/v1/zones/${zoneCode}/products?cat=${urlCat}&scene=${urlScene}&keyword=${urlKeyword}&page=${urlPage}&locale=${locale}`,
    () =>
      zonesApi.products(zoneCode, {
        zone_category_code: urlCat || undefined,
        scene_code: urlScene || undefined,
        keyword: urlKeyword || undefined,
        page: urlPage,
        size: PAGE_SIZE,
      }),
    { revalidateOnFocus: false }
  );

  const clearAll = () => updateParams({ cat: undefined, scene: undefined, keyword: undefined, page: undefined });

  // 两条轴:场景行(kind=SCENE,可多挂)在上,大类行(kind=CATEGORY)在下;没有场景的专区(常用材料)不渲染场景行。
  const scenes = useMemo(() => (categories ?? []).filter((c) => c.kind === "SCENE"), [categories]);
  const cats = useMemo(() => (categories ?? []).filter((c) => c.kind !== "SCENE"), [categories]);

  const activeChips = useMemo(() => {
    const out: { key: string; axis: string; label: string; clear: () => void }[] = [];
    const scene = scenes.find((c) => c.code === urlScene);
    if (scene) out.push({ key: "scene", axis: t("sceneChipAxis"), label: scene.name, clear: () => handleSceneSelect("") });
    const cat = cats.find((c) => c.code === urlCat);
    if (cat) out.push({ key: "cat", axis: t("categoryChipAxis"), label: cat.name, clear: () => handleCategorySelect("") });
    if (urlKeyword) out.push({ key: "kw", axis: t("keywordChipAxis"), label: urlKeyword, clear: () => updateParams({ keyword: undefined, page: undefined }) });
    return out;
  }, [scenes, cats, urlScene, urlCat, urlKeyword, handleSceneSelect, handleCategorySelect, updateParams, t]);

  const productHref = useMemo(
    () => (productId: number) => `/zone/${zoneCode}/products/${productId}`,
    [zoneCode]
  );

  return (
    <PublicLayout>
      <div className="space-y-4">
        {/* 场景导航(第二条轴) */}
        {!categoriesLoading && scenes.length > 0 && (
          <ZoneCategoryNav
            categories={scenes}
            activeCode={urlScene}
            allLabel={t("allScenes")}
            label={t("sceneRowLabel")}
            onSelect={handleSceneSelect}
          />
        )}

        {/* 大类导航 */}
        {!categoriesLoading && cats.length > 0 && (
          <ZoneCategoryNav
            categories={cats}
            activeCode={urlCat}
            allLabel={t("allCategories")}
            label={t("categoryRowLabel")}
            onSelect={handleCategorySelect}
          />
        )}

        {/* 结果计数 + 已选条件:两轴叠加后用户要知道筛了什么、剩多少,并能一键清掉 */}
        {productData && (
          <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-2" aria-live="polite">
            <span className="font-semibold text-ink">{t("resultCount", { total: productData.total })}</span>
            {activeChips.length > 0 && (
              <>
                <span className="text-muted">· {t("activeFilters")}</span>
                {activeChips.map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    onClick={chip.clear}
                    aria-label={`${t("clearFilters")}: ${chip.axis} ${chip.label}`}
                    className="inline-flex h-7 items-center gap-1 rounded-full bg-teal-50 px-3 font-medium text-teal-900 hover:bg-teal-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
                  >
                    {/* 轴名前缀:两条轴的已选值并排时,只写名字会看成同一种东西 */}
                    <span className="font-normal text-muted">{chip.axis}：</span>
                    {chip.label}
                    <X className="h-3.5 w-3.5" aria-hidden />
                  </button>
                ))}
                {activeChips.length > 1 && (
                  <button type="button" onClick={clearAll} className="font-medium text-teal-700 underline-offset-2 hover:underline">
                    {t("clearFilters")}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* 商品网格 */}
        <ProductGrid
          products={productData?.items ?? []}
          categoryTree={noCategoryTree}
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
