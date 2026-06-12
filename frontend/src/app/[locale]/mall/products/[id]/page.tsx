"use client";

import React, { Suspense, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import {
  ArrowLeft,
  ChevronRight,
  Home,
  ShoppingCart,
  MessageCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import Link from "next/link";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { getProduct, type ProductPublicDetail, type AttrGroup, type AttrItem } from "@/lib/api/products";
import { ProductGallery } from "@/components/mall/ProductGallery";

// ---- 面包屑 ----

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

// ---- 色板缩略图 ----

function SwatchThumb({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div className="flex h-[54px] w-[54px] items-center justify-center rounded-md border border-gray-200 bg-gray-50 text-xs text-gray-500">
        {alt || "—"}
      </div>
    );
  }

  return (
    <div className="relative">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        onError={() => setFailed(true)}
        className="h-[54px] w-[54px] rounded-md border border-gray-300 object-cover"
        loading="lazy"
      />
      {alt && (
        <span className="mt-0.5 block text-center text-[10px] text-gray-500 leading-tight">
          {alt}
        </span>
      )}
    </div>
  );
}

// ---- 右侧面板属性(色板/chip) ----

function hasSwatchImages(item: AttrItem): boolean {
  return item.values.some((v) => v.value_type === "image" && v.swatch_image);
}

function InlineAttrItem({ item }: { item: AttrItem }) {
  const isSwatch = hasSwatchImages(item);

  return (
    <div className="mb-4">
      <div className="mb-1.5 text-xs font-semibold text-gray-600">{item.key}</div>
      {isSwatch ? (
        <div className="flex flex-wrap gap-2">
          {item.values.map((v, i) =>
            v.value_type === "image" && v.swatch_image ? (
              <SwatchThumb key={i} src={v.swatch_image} alt={v.value} />
            ) : (
              <div
                key={i}
                className="flex h-[54px] w-[54px] items-center justify-center rounded-md border border-gray-200 bg-gray-50 text-xs text-gray-600"
              >
                {v.value}
              </div>
            )
          )}
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {item.values.map((v, i) => (
            <span
              key={i}
              className="rounded-md border-[1.5px] border-gray-200 bg-white px-3.5 py-1.5 text-xs text-gray-600"
            >
              {v.value}
              {item.unit ? ` ${item.unit}` : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Tab: 产品规格 ----

type TabKey = "specifications" | "description" | "gallery";

function SpecificationsTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  const baseRows: { label: string; value: string }[] = [];
  if (product.origin) baseRows.push({ label: t("detail.origin"), value: product.origin });
  if (product.brand) baseRows.push({ label: t("detail.brand"), value: product.brand });
  if (product.hs_code) baseRows.push({ label: t("detail.hsCode"), value: product.hs_code });

  const groups = product.attribute_groups;

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
          {groups.map((group) => {
            // attr_group 名翻译:优先查 i18n key,未匹配时原样展示
            const groupKey = `detail.attrGroup_${group.group}` as Parameters<typeof t>[0];
            let groupLabel: string;
            try { groupLabel = t(groupKey); } catch { groupLabel = group.group; }
            // 如果 t() 返回的就是 key 本身说明没匹配,用原值
            if (groupLabel === groupKey || groupLabel.startsWith("detail.")) groupLabel = group.group;

            return (
            <React.Fragment key={group.group}>
              {/* 分组标题行 */}
              <tr>
                <td
                  colSpan={2}
                  className="border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-semibold text-gray-500"
                >
                  {groupLabel}
                </td>
              </tr>
              {group.items.map((item) => (
                <tr key={`${group.group}-${item.key}`}>
                  <td className="border border-gray-200 px-3 py-2 text-gray-600">{item.key}</td>
                  <td className="border border-gray-200 px-3 py-2">
                    {item.values.map((v) => v.value).join(" · ")}
                    {item.unit ? ` ${item.unit}` : ""}
                  </td>
                </tr>
              ))}
            </React.Fragment>
          );
          })}
        </tbody>
      </table>
      {baseRows.length === 0 && groups.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">{t("detail.noSpecs")}</p>
      )}
    </div>
  );
}

// ---- Tab: 产品描述 ----

function DescriptionTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  return (
    <div className="space-y-4">
      {product.selling_points && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">{t("detail.sellingPoints")}</h4>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
            {product.selling_points}
          </div>
        </div>
      )}
      {product.description && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">{t("detail.description")}</h4>
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

// ---- Tab: 产品图片 ----

function GalleryTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");
  const images = product.images
    .filter((img) => img.sku_id == null)
    .sort((a, b) => a.sort_order - b.sort_order);

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

// ---- 底部:商品详情(全部图片) ----

function ProductDetailImages({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");
  const allImages = product.images
    .filter((img) => img.sku_id == null)
    .sort((a, b) => a.sort_order - b.sort_order);

  if (allImages.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl border border-gray-200 bg-white">
      <div className="border-b border-gray-200 px-5 py-3">
        <h2 className="text-sm font-semibold text-gray-800">{t("detail.productDetail")}</h2>
      </div>
      <div className="p-5">
        <div className="mx-auto max-w-3xl space-y-4">
          {allImages.map((img) => (
            <div key={img.id} className="overflow-hidden rounded-lg border border-gray-100 bg-gray-50">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.full_url}
                alt=""
                className="mx-auto w-full object-contain"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      </div>
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

  const { tree: categoryTree } = useCategoryTree();

  const { data: product, error, isLoading } = useSWR(
    id ? `/api/v1/products/${id}?locale=${locale}` : null,
    () => getProduct(id),
    { revalidateOnFocus: false }
  );

  const [activeTab, setActiveTab] = useState<TabKey>("specifications");

  const breadcrumb = useMemo(() => {
    if (!product || !categoryTree.length) return [];
    return buildBreadcrumb(categoryTree, product.category_code);
  }, [product, categoryTree]);

  // 多值属性提到右侧面板(颜色/厚度等)
  const inlineAttrs = useMemo(() => {
    if (!product) return [];
    const items: AttrItem[] = [];
    for (const group of product.attribute_groups) {
      for (const item of group.items) {
        if (item.values.length > 1 || hasSwatchImages(item)) {
          items.push(item);
        }
      }
    }
    return items;
  }, [product]);

  // ---- 加载/错误态 ----
  if (isLoading) {
    return (
      <PublicLayout>
        <div className="flex flex-col lg:flex-row gap-5">
          <CategorySidebar />
          <div className="flex flex-1 min-h-[400px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[#0D4D4D]" />
          </div>
        </div>
      </PublicLayout>
    );
  }

  if (error || !product) {
    return (
      <PublicLayout>
        <div className="flex flex-col lg:flex-row gap-5">
          <CategorySidebar />
          <div className="flex-1">
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
          </div>
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
      <div className="flex flex-col lg:flex-row gap-5">
        <CategorySidebar activeCategoryCode={product.category_code} />
        <div className="flex-1 min-w-0">

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

      {/* ===== 主体:左图 + 右信息(与旧版一致) ===== */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* 左:图片轮播(排除 DETAIL 类型) */}
          <ProductGallery
            images={product.images.filter((img) => img.sku_id == null && img.image_type !== "DETAIL")}
            isFeatured={product.is_featured}
          />

          {/* 右:信息面板 */}
          <div className="min-w-0 flex-1">
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

            {/* 商品描述/卖点 — 醒目展示 */}
            {(product.selling_points || product.description) && (
              <div className="mt-3 rounded-lg border border-[#0D4D4D]/10 bg-[#0D4D4D]/[0.03] px-4 py-3">
                {product.selling_points && (
                  <div className="text-sm leading-relaxed text-gray-800">
                    <span className="mr-1.5 text-xs font-semibold text-[#0D4D4D]">✦ {t("detail.sellingPoints")}</span>
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

            {/* 基础信息(产地/品牌) */}
            {(product.origin || product.brand) && (
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
                {product.origin && (
                  <span>{t("detail.origin")}: <span className="font-medium text-gray-700">{product.origin}</span></span>
                )}
                {product.brand && (
                  <span>{t("detail.brand")}: <span className="font-medium text-gray-700">{product.brand}</span></span>
                )}
              </div>
            )}

            {/* 属性:颜色色板 / 厚度 chip(多值项) */}
            {inlineAttrs.length > 0 && (
              <div className="mt-4">
                {inlineAttrs.map((item) => (
                  <InlineAttrItem key={item.key} item={item} />
                ))}
              </div>
            )}

            {/* 操作按钮 */}
            <div className="mt-4 flex flex-wrap gap-2.5">
              {/* TODO: 询价行粒度(SPU vs SPU+规格)+ 购物车条目结构待定 */}
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#0D4D4D] px-6 py-3 text-sm font-semibold text-white opacity-50 cursor-not-allowed"
                title={t("detail.comingSoon")}
              >
                <ShoppingCart className="h-4 w-4" />
                {t("detail.addToInquiry")}
              </button>
              {/* TODO: WhatsApp 平台运营号/链接配置化 */}
              <a
                href="https://wa.me/255697123456"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#25D366] px-6 py-3 text-sm font-semibold text-white hover:bg-[#20bd5a] transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                WhatsApp {t("detail.contactPlatform")}
              </a>
            </div>
            <p className="mt-1.5 text-[11px] text-gray-400">{t("detail.comingSoon")}</p>
          </div>
        </div>
      </div>

      {/* ===== Tab 区(与旧版一致:产品规格 / 产品描述 / 产品图片) ===== */}
      <div className="mt-4 rounded-xl border border-gray-200 bg-white">
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
        <div className="p-5">
          {activeTab === "specifications" && <SpecificationsTab product={product} />}
          {activeTab === "description" && <DescriptionTab product={product} />}
          {activeTab === "gallery" && <GalleryTab product={product} />}
        </div>
      </div>

      {/* ===== 商品详情:所有图片竖排展示(外观/细节/详情图) ===== */}
      <ProductDetailImages product={product} />

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
