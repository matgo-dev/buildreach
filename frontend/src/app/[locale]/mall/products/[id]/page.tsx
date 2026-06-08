"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import {
  ArrowLeft,
  ChevronRight,
  Home,
  ShoppingCart,
  Mail,
  MessageCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import Link from "next/link";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { getProduct, type ProductPublicDetail, type SkuPublic } from "@/lib/api/products";
import { formatCurrency } from "@/lib/formatters";

import { ProductGallery } from "@/components/mall/ProductGallery";
import {
  SkuSelector,
  extractDimensions,
  getDefaultSelection,
  locateSku,
  type DimensionSelection,
} from "@/components/mall/SkuSelector";
import { PriceTiers, matchTier } from "@/components/mall/PriceTiers";
import { QuantityInput } from "@/components/mall/QuantityInput";

// ---- 面包屑:从品类树解析路径 ----

function buildBreadcrumb(
  tree: CategoryTreeNode[],
  categoryCode: string
): { code: string; name: string }[] {
  const path: { code: string; name: string }[] = [];

  function dfs(nodes: CategoryTreeNode[]): boolean {
    for (const node of nodes) {
      path.push({ code: node.code, name: node.name });
      if (node.code === categoryCode) return true;
      if (node.children && dfs(node.children)) return true;
      path.pop();
    }
    return false;
  }

  dfs(tree);
  return path;
}

// ---- Tab 区 ----

type TabKey = "specifications" | "description" | "gallery";

function SpecificationsTab({
  product,
  selectedSku,
}: {
  product: ProductPublicDetail;
  selectedSku: SkuPublic | null;
}) {
  const t = useTranslations("mall");

  // SPU 级属性
  const spuAttrs = product.attributes.filter((a) => !a.sku_id);
  // 选中 SKU 的属性(非差异维度的,即所有 SKU 都一样的)
  const skuAttrs = selectedSku?.attributes ?? [];

  // 合并:SPU 属性 + SKU 属性(去重)
  const allAttrs = [...spuAttrs];
  for (const attr of skuAttrs) {
    if (!allAttrs.some((a) => a.attr_key === attr.attr_key)) {
      allAttrs.push(attr);
    }
  }
  allAttrs.sort((a, b) => a.sort_order - b.sort_order);

  // 基础信息行
  const baseRows: { label: string; value: string }[] = [];
  if (product.origin) baseRows.push({ label: t("detail.origin"), value: product.origin });
  if (product.brand) baseRows.push({ label: t("detail.brand"), value: product.brand });
  if (product.hs_code) baseRows.push({ label: t("detail.hsCode"), value: product.hs_code });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="w-1/3 border border-gray-200 bg-gray-50 px-3 py-2 text-left font-semibold text-gray-700">
              {t("detail.specName")}
            </th>
            <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left font-semibold text-gray-700">
              {t("detail.specValue")}
            </th>
          </tr>
        </thead>
        <tbody>
          {baseRows.map((row) => (
            <tr key={row.label}>
              <td className="border border-gray-200 px-3 py-2 text-gray-600">{row.label}</td>
              <td className="border border-gray-200 px-3 py-2">{row.value}</td>
            </tr>
          ))}
          {allAttrs.map((attr) => (
            <tr key={attr.attr_key}>
              <td className="border border-gray-200 px-3 py-2 text-gray-600">
                {attr.display_name || attr.attr_key}
              </td>
              <td className="border border-gray-200 px-3 py-2">
                {attr.attr_value}
                {attr.attr_unit ? ` ${attr.attr_unit}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {baseRows.length === 0 && allAttrs.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">{t("detail.noSpecs")}</p>
      )}
    </div>
  );
}

function DescriptionTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  return (
    <div className="space-y-4">
      {product.selling_points && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">
            {t("detail.sellingPoints")}
          </h4>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
            {product.selling_points}
          </div>
        </div>
      )}
      {product.description && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">
            {t("detail.description")}
          </h4>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
            {product.description}
          </div>
        </div>
      )}
      {!product.description && !product.selling_points && (
        <p className="py-8 text-center text-sm text-gray-400">{t("detail.noDescription")}</p>
      )}
    </div>
  );
}

function GalleryTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");
  const images = [...product.images].sort((a, b) => a.sort_order - b.sort_order);

  if (images.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-400">{t("detail.noImages")}</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {images.map((img) => (
        <div
          key={img.id}
          className="relative aspect-square overflow-hidden rounded-lg border border-gray-200 bg-gray-50"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={img.full_url}
            alt=""
            className="h-full w-full object-contain"
            loading="lazy"
          />
        </div>
      ))}
    </div>
  );
}

// ---- 主内容 ----

function ProductDetailContent() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const id = Number(params.id);

  // 品类树
  const { tree: categoryTree } = useCategoryTree();

  // SWR 取详情
  const { data: product, error, isLoading } = useSWR(
    id ? `/api/v1/products/${id}?locale=${locale}` : null,
    () => getProduct(id),
    { revalidateOnFocus: false }
  );

  // SKU 选择器状态
  const activeSkus = useMemo(
    () => (product?.skus ?? []).filter((s) => s.status === "ACTIVE"),
    [product]
  );

  const dimensions = useMemo(() => extractDimensions(activeSkus), [activeSkus]);

  const [selection, setSelection] = useState<DimensionSelection>({});

  // 产品加载完成后初始化默认选中
  useEffect(() => {
    if (activeSkus.length > 0 && dimensions.length >= 0) {
      setSelection(getDefaultSelection(activeSkus, dimensions));
    }
  }, [activeSkus, dimensions]);

  const selectedSku = useMemo(
    () => locateSku(activeSkus, dimensions, selection),
    [activeSkus, dimensions, selection]
  );

  // 数量
  const [quantity, setQuantity] = useState<number>(0);

  // 选中 SKU 变化时重置数量为 MOQ
  useEffect(() => {
    if (selectedSku) {
      setQuantity(selectedSku.moq);
    }
  }, [selectedSku?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // 价格计算
  const priceDisplay = useMemo(() => {
    if (!product) return null;

    // 未选 SKU → SPU 级区间
    if (!selectedSku) {
      if (product.price_min !== null && product.price_max !== null) {
        return {
          type: "range" as const,
          min: product.price_min,
          max: product.price_max,
          currency: activeSkus[0]?.currency ?? "USD",
        };
      }
      return null;
    }

    const sku = selectedSku;

    // 已选 SKU + 有数量 → 匹配阶梯价
    if (quantity > 0 && sku.price_tiers.length > 0) {
      const tier = matchTier(sku.price_tiers, quantity);
      if (tier) {
        return {
          type: "exact" as const,
          price: tier.unit_price,
          currency: tier.currency,
          tierLabel: tier.label,
        };
      }
    }

    // 已选 SKU,无阶梯价匹配 → SKU 级区间或 price_min
    if (sku.price_min !== null) {
      if (sku.price_max !== null && sku.price_max !== sku.price_min) {
        return {
          type: "range" as const,
          min: sku.price_min,
          max: sku.price_max,
          currency: sku.currency,
        };
      }
      return {
        type: "exact" as const,
        price: sku.price_min,
        currency: sku.currency,
      };
    }

    return null;
  }, [product, selectedSku, quantity, activeSkus]);

  // 小计
  const subtotal = useMemo(() => {
    if (!selectedSku || quantity <= 0) return null;
    if (priceDisplay?.type === "exact") {
      return {
        amount: quantity * priceDisplay.price,
        currency: priceDisplay.currency,
      };
    }
    return null;
  }, [selectedSku, quantity, priceDisplay]);

  // Tab 状态
  const [activeTab, setActiveTab] = useState<TabKey>("specifications");

  // 面包屑
  const breadcrumb = useMemo(() => {
    if (!product || !categoryTree.length) return [];
    return buildBreadcrumb(categoryTree, product.category_code);
  }, [product, categoryTree]);

  // SKU 专属图
  const skuImages = useMemo(
    () => (selectedSku?.images.length ? selectedSku.images : undefined),
    [selectedSku]
  );

  // 单位标签
  const unitLabel = selectedSku
    ? t(`unit_${selectedSku.unit}` as Parameters<typeof t>[0])
    : "";

  // ---- 加载/错误态 ----
  if (isLoading) {
    return (
      <PublicLayout>
        <div className="flex min-h-[400px] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#0D4D4D]" />
        </div>
      </PublicLayout>
    );
  }

  if (error || !product) {
    return (
      <PublicLayout>
        <div className="rounded-xl border border-gray-200 bg-white py-20 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-gray-300" />
          <h2 className="text-lg font-semibold text-gray-700">{t("detail.notFound")}</h2>
          <p className="mt-2 text-sm text-gray-400">{t("detail.notFoundHint")}</p>
          <button
            onClick={() => router.push(`/${locale}/mall`)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-[#0D4D4D] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d]"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("detail.backToList")}
          </button>
        </div>
      </PublicLayout>
    );
  }

  // ---- 正常渲染 ----

  const tabItems: { key: TabKey; label: string }[] = [
    { key: "specifications", label: t("detail.tabSpecs") },
    { key: "description", label: t("detail.tabDescription") },
    { key: "gallery", label: t("detail.tabGallery") },
  ];

  return (
    <PublicLayout>
      {/* 面包屑 */}
      <nav className="mb-4 flex items-center gap-1.5 text-xs text-gray-400">
        <Link
          href={`/${locale}/mall`}
          className="flex items-center gap-1 text-[#0D4D4D] transition-colors hover:underline"
        >
          <Home className="h-3 w-3" />
          Home
        </Link>
        {breadcrumb.map((crumb) => (
          <React.Fragment key={crumb.code}>
            <ChevronRight className="h-3 w-3" />
            <Link
              href={`/${locale}/mall?cat=${crumb.code}`}
              className="text-[#0D4D4D] transition-colors hover:underline"
            >
              {crumb.name}
            </Link>
          </React.Fragment>
        ))}
        <ChevronRight className="h-3 w-3" />
        <span className="font-medium text-gray-700">{product.name}</span>
      </nav>

      {/* 主体:左图 + 右信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* 左:图片轮播 */}
          <ProductGallery
            images={product.images}
            skuImages={skuImages}
            isFeatured={product.is_featured}
          />

          {/* 右:信息面板 */}
          <div className="min-w-0 flex-1">
            {/* SPU 编码 + 商品名 */}
            <p className="text-[11px] text-gray-400">SPU: {product.spu_code}</p>
            <h1 className="text-xl font-bold text-gray-800">{product.name}</h1>

            {/* 认证徽章 */}
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

            {/* 价格区 */}
            <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
              {priceDisplay ? (
                <>
                  <div>
                    {priceDisplay.type === "range" ? (
                      <>
                        <span className="text-2xl font-bold text-[#0D4D4D]">
                          {formatCurrency(priceDisplay.min, priceDisplay.currency, locale, {
                            maximumFractionDigits: 2,
                          })}
                        </span>
                        <span className="mx-1 text-lg text-gray-400">~</span>
                        <span className="text-2xl font-bold text-[#0D4D4D]">
                          {formatCurrency(priceDisplay.max, priceDisplay.currency, locale, {
                            maximumFractionDigits: 2,
                          })}
                        </span>
                        {selectedSku && (
                          <span className="ml-2 text-sm text-gray-500">/ {unitLabel}</span>
                        )}
                      </>
                    ) : (
                      <>
                        <span className="text-[28px] font-bold text-[#0D4D4D]">
                          {formatCurrency(priceDisplay.price, priceDisplay.currency, locale, {
                            maximumFractionDigits: 2,
                          })}
                        </span>
                        <span className="ml-1 text-sm text-gray-500">/ {unitLabel}</span>
                      </>
                    )}
                  </div>
                  {selectedSku && priceDisplay.type === "exact" && quantity > 0 && (
                    <p className="mt-1 text-[11px] text-gray-500">
                      {t("detail.volumePriceHint", { qty: quantity, unit: unitLabel })}
                    </p>
                  )}
                </>
              ) : (
                <span className="text-lg text-gray-400">{t("noPrice")}</span>
              )}
            </div>

            {/* SKU 属性选择器 */}
            {activeSkus.length > 0 && (
              <div className="mt-4">
                <SkuSelector
                  skus={activeSkus}
                  selection={selection}
                  onSelectionChange={setSelection}
                />
              </div>
            )}

            {/* 选中 SKU 摘要 */}
            {selectedSku && (
              <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs">
                <div>
                  <div className="text-[10px] text-gray-400">SKU Code</div>
                  <div className="font-semibold text-gray-800">
                    {selectedSku.sku_code}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-400">MOQ</div>
                  <div className="font-semibold text-gray-800">
                    {selectedSku.moq} {unitLabel}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-gray-400">Lead Time</div>
                  <div className="font-semibold text-gray-800">
                    {selectedSku.lead_time_min && selectedSku.lead_time_max
                      ? selectedSku.lead_time_min === selectedSku.lead_time_max
                        ? t("leadTimeDaysSingle", { days: selectedSku.lead_time_min })
                        : t("leadTimeDays", {
                            min: selectedSku.lead_time_min,
                            max: selectedSku.lead_time_max,
                          })
                      : "-"}
                  </div>
                </div>
              </div>
            )}

            {/* 阶梯价表 */}
            {selectedSku && selectedSku.price_tiers.length > 0 && (
              <PriceTiers
                tiers={selectedSku.price_tiers}
                unit={selectedSku.unit}
                quantity={quantity}
              />
            )}

            {/* 数量输入 */}
            {selectedSku && (
              <div className="mt-4">
                <QuantityInput
                  value={quantity}
                  onChange={setQuantity}
                  moq={selectedSku.moq}
                  unit={selectedSku.unit}
                />
              </div>
            )}

            {/* 小计 */}
            {subtotal && quantity >= (selectedSku?.moq ?? 0) && (
              <div className="mt-2 flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-2.5">
                <span className="text-sm font-medium text-green-700">
                  {t("detail.subtotal")}
                </span>
                <span className="text-xl font-bold text-green-700">
                  {formatCurrency(subtotal.amount, subtotal.currency, locale, {
                    maximumFractionDigits: 2,
                  })}
                </span>
              </div>
            )}

            {/* 操作按钮(占位灰显) */}
            <div className="mt-4 flex flex-wrap gap-2.5">
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg bg-gray-300 px-6 py-3 text-sm font-semibold text-white cursor-not-allowed"
                title={t("comingSoon")}
              >
                <ShoppingCart className="h-4 w-4" />
                {t("detail.addToBasket")}
              </button>
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg border-2 border-gray-300 px-6 py-3 text-sm font-semibold text-gray-400 cursor-not-allowed"
                title={t("comingSoon")}
              >
                <Mail className="h-4 w-4" />
                {t("detail.requestQuoteNow")}
              </button>
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg bg-gray-300 px-5 py-3 text-sm font-semibold text-white cursor-not-allowed"
                title={t("comingSoon")}
              >
                <MessageCircle className="h-4 w-4" />
                WhatsApp
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Tab 区 */}
      <div className="mt-4 rounded-xl border border-gray-200 bg-white">
        {/* Tab 头 */}
        <div className="flex border-b border-gray-200">
          {tabItems.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-5 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-b-2 border-[#0D4D4D] text-[#0D4D4D]"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab 内容 */}
        <div className="p-5">
          {activeTab === "specifications" && (
            <SpecificationsTab product={product} selectedSku={selectedSku} />
          )}
          {activeTab === "description" && <DescriptionTab product={product} />}
          {activeTab === "gallery" && <GalleryTab product={product} />}
        </div>
      </div>
    </PublicLayout>
  );
}

export default function ProductDetailPage() {
  return (
    <RouteGuard allowRoles={["BUYER", "OPERATOR"]}>
      <Suspense fallback={null}>
        <ProductDetailContent />
      </Suspense>
    </RouteGuard>
  );
}
