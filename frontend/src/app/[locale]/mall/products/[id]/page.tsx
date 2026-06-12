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
import { getProduct, type ProductPublicDetail, type AttrGroup } from "@/lib/api/products";

import { ProductGallery } from "@/components/mall/ProductGallery";

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

// ---- 属性分组只读表 ----

/** 色板缩略图 — 加载失败回退为文本 */
function SwatchThumb({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return <span className="text-sm text-gray-800">{alt || "—"}</span>;
  }

  return (
    <div className="group/swatch relative inline-block">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        onError={() => setFailed(true)}
        className="h-12 w-12 rounded-md border border-gray-200 object-cover"
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

function AttributeGroups({ groups }: { groups: AttrGroup[] }) {
  const t = useTranslations("mall");

  if (groups.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-400">{t("detail.noSpecs")}</p>;
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.group}>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">{group.group}</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {group.items.map((item) => {
                  const hasImage = item.values.some((v) => v.value_type === "image" && v.swatch_image);

                  return (
                    <tr key={item.key} className="border-b border-gray-100">
                      <td className="w-1/3 px-3 py-2 align-top text-gray-500">{item.key}</td>
                      <td className="px-3 py-2 text-gray-800">
                        {hasImage ? (
                          <div className="flex flex-wrap gap-2">
                            {item.values.map((v, i) =>
                              v.value_type === "image" && v.swatch_image ? (
                                <SwatchThumb key={i} src={v.swatch_image} alt={v.value} />
                              ) : (
                                <span key={i} className="self-center text-sm">{v.value}</span>
                              )
                            )}
                          </div>
                        ) : (
                          <>
                            {item.values.map((v) => v.value).join(", ")}
                            {item.unit ? ` ${item.unit}` : ""}
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Tab 区 ----

type TabKey = "specifications" | "description" | "gallery";

function SpecificationsTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  // 基础信息行
  const baseRows: { label: string; value: string }[] = [];
  if (product.origin) baseRows.push({ label: t("detail.origin"), value: product.origin });
  if (product.brand) baseRows.push({ label: t("detail.brand"), value: product.brand });
  if (product.hs_code) baseRows.push({ label: t("detail.hsCode"), value: product.hs_code });

  return (
    <div className="space-y-4">
      {/* 基础信息 */}
      {baseRows.length > 0 && (
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
            </tbody>
          </table>
        </div>
      )}

      {/* 分组属性 */}
      <AttributeGroups groups={product.attribute_groups} />
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
  const images = product.images.filter((img) => img.sku_id == null).sort((a, b) => a.sort_order - b.sort_order);

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

  // Tab 状态
  const [activeTab, setActiveTab] = useState<TabKey>("specifications");

  // 面包屑
  const breadcrumb = useMemo(() => {
    if (!product || !categoryTree.length) return [];
    return buildBreadcrumb(categoryTree, product.category_code);
  }, [product, categoryTree]);

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

      {/* 主体:左图 + 右信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* 左:图片轮播 */}
          <ProductGallery
            images={product.images.filter((img) => img.sku_id == null)}
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

            {/* 分组属性只读展示 */}
            {product.attribute_groups.length > 0 && (
              <div className="mt-4">
                <AttributeGroups groups={product.attribute_groups} />
              </div>
            )}

            {/* 操作按钮 */}
            <div className="mt-6 flex flex-wrap gap-2.5">
              {/* 加入询价单 — 置灰,机制待定 */}
              {/* TODO: 询价行粒度(SPU vs SPU+规格)+ 购物车条目结构待定,启用后接 addCartItem */}
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg bg-gray-300 px-6 py-3 text-sm font-semibold text-white cursor-not-allowed"
                title={t("detail.comingSoon")}
              >
                <ShoppingCart className="h-4 w-4" />
                {t("detail.addToInquiry")}
              </button>

              {/* 联系平台 WhatsApp — 保留(买家↔运营) */}
              {/* TODO: WhatsApp 平台运营号/链接配置化 */}
              <a
                href="https://wa.me/255697123456"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#25D366] px-6 py-3 text-sm font-semibold text-white hover:bg-[#20bd5a] transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                {t("detail.contactPlatform")}
              </a>

              {/* 发起询价 — 置灰 */}
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-6 py-3 text-sm font-semibold text-gray-400 cursor-not-allowed"
                title={t("detail.comingSoon")}
              >
                {t("detail.startInquiry")}
              </button>
            </div>

            {/* 置灰提示 */}
            <p className="mt-2 text-xs text-gray-400">{t("detail.comingSoon")}</p>
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
            <SpecificationsTab product={product} />
          )}
          {activeTab === "description" && <DescriptionTab product={product} />}
          {activeTab === "gallery" && <GalleryTab product={product} />}
        </div>
      </div>
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
