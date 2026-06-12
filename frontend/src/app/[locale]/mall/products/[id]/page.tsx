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

// ---- 右侧面板:属性以色板/chip 渲染 ----

/** 判断一个 AttrItem 是否含有色板图 */
function hasSwatchImages(item: AttrItem): boolean {
  return item.values.some((v) => v.value_type === "image" && v.swatch_image);
}

/** 右侧面板中的属性展示:色板图渲染为缩略图,文本渲染为 chip */
function InlineAttrItem({ item }: { item: AttrItem }) {
  const isSwatch = hasSwatchImages(item);

  return (
    <div className="mb-4">
      <div className="mb-1.5 text-xs font-semibold text-gray-500">
        {item.key}
        {!isSwatch && <span className="ml-1 font-normal text-gray-400">({item.values.length})</span>}
      </div>
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
        <div className="flex flex-wrap gap-2">
          {item.values.map((v, i) => (
            <span
              key={i}
              className="rounded-md border border-gray-200 px-3 py-1.5 text-xs text-gray-700"
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

// ---- 规格参数表(底部分段) ----

function SpecTable({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  const baseRows: { label: string; value: string }[] = [];
  if (product.origin) baseRows.push({ label: t("detail.origin"), value: product.origin });
  if (product.brand) baseRows.push({ label: t("detail.brand"), value: product.brand });
  if (product.hs_code) baseRows.push({ label: t("detail.hsCode"), value: product.hs_code });

  const groups = product.attribute_groups;
  const hasContent = baseRows.length > 0 || groups.length > 0;

  if (!hasContent) return null;

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200">
      {/* 基础信息行 */}
      {baseRows.length > 0 && (
        <>
          <div className="bg-gray-50 px-3 py-2 text-xs font-semibold text-gray-500">
            {t("detail.tabSpecs")}
          </div>
          {baseRows.map((row) => (
            <div key={row.label} className="flex border-t border-gray-100 px-3 py-2 text-sm">
              <span className="w-[130px] shrink-0 text-gray-500">{row.label}</span>
              <span className="text-gray-800">{row.value}</span>
            </div>
          ))}
        </>
      )}

      {/* 按 attr_group 分组 */}
      {groups.map((group) => (
        <React.Fragment key={group.group}>
          <div className="border-t border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold text-gray-500">
            {group.group}
          </div>
          {group.items.map((item) => (
            <div key={item.key} className="flex border-t border-gray-100 px-3 py-2 text-sm">
              <span className="w-[130px] shrink-0 text-gray-500">{item.key}</span>
              <span className="text-gray-800">
                {item.values.map((v) => v.value).join(" · ")}
                {item.unit ? ` ${item.unit}` : ""}
              </span>
            </div>
          ))}
        </React.Fragment>
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

  const { tree: categoryTree } = useCategoryTree();

  const { data: product, error, isLoading } = useSWR(
    id ? `/api/v1/products/${id}?locale=${locale}` : null,
    () => getProduct(id),
    { revalidateOnFocus: false }
  );

  const breadcrumb = useMemo(() => {
    if (!product || !categoryTree.length) return [];
    return buildBreadcrumb(categoryTree, product.category_code);
  }, [product, categoryTree]);

  // 从属性中提取适合右侧面板展示的项(多值的,如颜色/厚度)
  const inlineAttrs = useMemo(() => {
    if (!product) return [];
    const items: AttrItem[] = [];
    for (const group of product.attribute_groups) {
      for (const item of group.items) {
        // 多值项或有色板图的放右侧面板展示
        if (item.values.length > 1 || hasSwatchImages(item)) {
          items.push(item);
        }
      }
    }
    return items;
  }, [product]);

  // 详情大图(DETAIL 类型)
  const detailImages = useMemo(() => {
    if (!product) return [];
    return product.images
      .filter((img) => img.image_type === "DETAIL" && img.sku_id == null)
      .sort((a, b) => a.sort_order - b.sort_order);
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

      {/* ===== 主区:左图 + 右信息 ===== */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* 左:图片 gallery */}
          <ProductGallery
            images={product.images.filter((img) => img.sku_id == null && img.image_type !== "DETAIL")}
            isFeatured={product.is_featured}
          />

          {/* 右:信息面板 */}
          <div className="min-w-0">
            <p className="text-[11px] text-gray-400">{product.spu_code}</p>
            <h1 className="text-lg font-semibold leading-snug text-gray-800">{product.name}</h1>
            {product.description && (
              <p className="mt-1 text-sm text-gray-500 line-clamp-3">{product.description}</p>
            )}

            {/* 认证徽章 */}
            {product.certifications && product.certifications.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {product.certifications.map((cert) => (
                  <span
                    key={cert}
                    className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
                  >
                    <span className="text-blue-500">✓</span> {cert}
                  </span>
                ))}
              </div>
            )}

            {/* 基础信息:产地/品牌/卖点 */}
            <div className="mt-3 space-y-1.5 text-sm">
              {product.origin && (
                <div className="flex">
                  <span className="w-16 shrink-0 text-gray-400">{t("detail.origin")}</span>
                  <span className="text-gray-700">{product.origin}</span>
                </div>
              )}
              {product.brand && (
                <div className="flex">
                  <span className="w-16 shrink-0 text-gray-400">{t("detail.brand")}</span>
                  <span className="text-gray-700">{product.brand}</span>
                </div>
              )}
              {product.selling_points && (
                <div className="flex">
                  <span className="w-16 shrink-0 text-gray-400">{t("detail.sellingPoints")}</span>
                  <span className="text-gray-700">{product.selling_points}</span>
                </div>
              )}
            </div>

            {/* 右侧面板内属性:颜色色板 / 厚度 chip 等(多值项) */}
            {inlineAttrs.length > 0 && (
              <div className="mt-5">
                {inlineAttrs.map((item) => (
                  <InlineAttrItem key={item.key} item={item} />
                ))}
              </div>
            )}

            {/* 操作按钮:询价篮 + WhatsApp 并排 */}
            <div className="mt-5 flex gap-3">
              {/* TODO: 询价行粒度(SPU vs SPU+规格)+ 购物车条目结构待定,启用后接 addCartItem */}
              <button
                type="button"
                disabled
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#0f3d36] px-4 py-3 text-sm font-semibold text-white opacity-50 cursor-not-allowed"
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
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#1aa951] px-4 py-3 text-sm font-semibold text-white hover:bg-[#158f43] transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                WhatsApp {t("detail.contactPlatform")}
              </a>
            </div>
            <p className="mt-1.5 text-[11px] text-gray-400">
              {t("detail.comingSoon")}
            </p>
          </div>
        </div>
      </div>

      {/* ===== 商品详情(文字 + DETAIL 图竖排) ===== */}
      {(detailImages.length > 0 || product.description || product.selling_points) && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-800">{t("detail.description")}</h2>

          {/* 文字描述在上 */}
          {product.selling_points && (
            <div className="mb-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
              {product.selling_points}
            </div>
          )}
          {product.description && (
            <div className="mb-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
              {product.description}
            </div>
          )}

          {/* DETAIL 图片竖排 */}
          {detailImages.length > 0 && (
            <div className="space-y-3">
              {detailImages.map((img) => (
                <div key={img.id} className="overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={img.full_url}
                    alt=""
                    className="w-full object-contain"
                    loading="lazy"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== 规格参数表(按 attr_group 分组) ===== */}
      {(product.attribute_groups.length > 0 || product.origin || product.brand) && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-gray-800">{t("detail.tabSpecs")}</h2>
          <SpecTable product={product} />
        </div>
      )}

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
