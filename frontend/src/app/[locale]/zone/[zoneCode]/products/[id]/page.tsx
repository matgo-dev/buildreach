"use client";

import React, { Suspense, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { ArrowLeft, AlertCircle, Loader2 } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { zonesApi, type ZoneProductDetail } from "@/lib/api/zones";
import { ProductGallery } from "@/components/mall/ProductGallery";
import {
  SkuSelector,
  extractDimensions,
  locateSku,
  getDefaultSelection,
  type DimensionSelection,
} from "@/components/mall/SkuSelector";

function formatPriceRange(min: number | null, max: number | null): string | null {
  if (min == null && max == null) return null;
  if (min != null && max != null && min !== max) return `${min} - ${max}`;
  return `${min ?? max}`;
}

function ZoneProductDetailContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("zone");
  const tMall = useTranslations("mall");
  const zoneCode = String(params.zoneCode);
  const id = Number(params.id);

  const { data: product, error, isLoading } = useSWR<ZoneProductDetail>(
    id ? `/api/v1/zones/${zoneCode}/products/${id}?locale=${locale}` : null,
    () => zonesApi.product(zoneCode, id),
    { revalidateOnFocus: false }
  );

  const dimensions = useMemo(() => (product ? extractDimensions(product.skus) : []), [product]);
  const [selection, setSelection] = useState<DimensionSelection>({});

  // 首次拿到数据时,用 is_default SKU 反推初始选中态
  const initializedRef = React.useRef(false);
  React.useEffect(() => {
    if (product && !initializedRef.current) {
      initializedRef.current = true;
      setSelection(getDefaultSelection(product.skus, dimensions));
    }
  }, [product, dimensions]);

  const selectedSku = useMemo(() => {
    if (!product) return null;
    return locateSku(product.skus, dimensions, selection);
  }, [product, dimensions, selection]);

  const galleryImages = useMemo(() => {
    if (!product) return [];
    return product.images.filter((img) => img.image_type !== "DETAIL");
  }, [product]);

  if (isLoading) {
    return (
      <PublicLayout>
        <div className="flex min-h-[400px] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#00505a]" />
        </div>
      </PublicLayout>
    );
  }

  if (error || !product) {
    return (
      <PublicLayout>
        <div className="rounded-xl border border-gray-200 bg-white py-20 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-gray-300" />
          <h2 className="text-lg font-semibold text-gray-700">{tMall("detail.notFound")}</h2>
          <button
            onClick={() => router.push(`/${locale}/zone/${zoneCode}`)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-[#00505a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d]"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("backToZone")}
          </button>
        </div>
      </PublicLayout>
    );
  }

  const priceRange = selectedSku
    ? formatPriceRange(selectedSku.price_min, selectedSku.price_max)
    : formatPriceRange(product.price_min ?? null, product.price_max ?? null);
  const moq = selectedSku?.moq ?? product.moq;
  const moqUnit = product.moq_unit || product.unit || "";

  return (
    <PublicLayout>
      {/* 简易面包屑 */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5 text-[12px] text-gray-500">
        <button
          onClick={() => router.push(`/${locale}/zone/${zoneCode}`)}
          className="hover:text-teal-700"
        >
          {t("backToZone")}
        </button>
        <span className="text-gray-300">/</span>
        <span className="max-w-[240px] truncate font-medium text-gray-700">{product.name}</span>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* 左:图片(选中 SKU 有专属图则优先展示) */}
          <ProductGallery images={galleryImages} skuImages={selectedSku?.images} />

          {/* 右:信息 + 规格切换 */}
          <div className="min-w-0 flex-1">
            <p className="text-[11px] text-gray-400">SPU: {product.spu_code}</p>
            <h1 className="text-xl font-bold text-gray-800">{product.name}</h1>

            {product.certifications && product.certifications.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {product.certifications.map((cert) => (
                  <span
                    key={cert}
                    className="rounded bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-800"
                  >
                    {cert}
                  </span>
                ))}
              </div>
            )}

            {(product.selling_points || product.description) && (
              <div className="mt-3 rounded-lg border border-[#00505a]/10 bg-[#00505a]/[0.03] px-4 py-3">
                {product.selling_points && (
                  <div className="text-sm leading-relaxed text-gray-800">
                    <span className="mr-1.5 text-xs font-semibold text-[#00505a]">✦ {tMall("detail.sellingPoints")}</span>
                    {product.selling_points}
                  </div>
                )}
                {product.description && (
                  <div className={`text-sm leading-relaxed text-gray-600 ${product.selling_points ? "mt-2" : ""}`}>
                    {product.description}
                  </div>
                )}
              </div>
            )}

            {/* 换购价 / MOQ */}
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
              {priceRange && (
                <span>
                  {t("price")}: <span className="font-medium text-gray-700">{priceRange}</span>
                </span>
              )}
              {moq != null && (
                <span>
                  {tMall("detail.moq")}: <span className="font-medium text-gray-700">{moq.toLocaleString()} {moqUnit}</span>
                </span>
              )}
              {product.origin && (
                <span>
                  {tMall("detail.origin")}: <span className="font-medium text-gray-700">{product.origin}</span>
                </span>
              )}
              {product.brand && (
                <span>
                  {tMall("detail.brand")}: <span className="font-medium text-gray-700">{product.brand}</span>
                </span>
              )}
            </div>

            {selectedSku?.sku_code && (
              <p className="mt-1 text-[11px] text-gray-400">SKU: {selectedSku.sku_code}</p>
            )}

            {/* 规格变体切换 */}
            {product.skus.length > 1 && (
              <div className="mt-4">
                <SkuSelector skus={product.skus} selection={selection} onSelectionChange={setSelection} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 规格参数 */}
      {product.attribute_groups.length > 0 && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{tMall("detail.tabSpecs")}</h3>
          <div className="space-y-4">
            {product.attribute_groups.map((group) => (
              <div key={group.group}>
                <dl className="grid grid-cols-1 gap-x-8 gap-y-1.5 sm:grid-cols-2">
                  {group.items.map((item) => (
                    <div key={item.key} className="flex text-sm">
                      <dt className="w-28 shrink-0 text-gray-500">{item.key}</dt>
                      <dd className="text-gray-800">
                        {item.values.map((v) => v.value).join(", ")}
                        {item.unit ? ` ${item.unit}` : ""}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 产品描述 */}
      {(product.detail_description || product.description) && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{tMall("detail.tabDescription")}</h3>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
            {product.detail_description || product.description}
          </div>
        </div>
      )}
    </PublicLayout>
  );
}

function ZoneProductDetailGated() {
  const params = useParams();
  const zoneCode = String(params.zoneCode);
  return (
    <RouteGuard requireZone={zoneCode}>
      <ZoneProductDetailContent />
    </RouteGuard>
  );
}

export default function ZoneProductDetailPage() {
  return (
    <Suspense fallback={null}>
      <ZoneProductDetailGated />
    </Suspense>
  );
}
