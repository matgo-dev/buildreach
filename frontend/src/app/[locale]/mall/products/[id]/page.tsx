"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
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

function InlineAttrItem({
  item,
  selectedValue,
  onSelect,
}: {
  item: AttrItem;
  selectedValue?: string;
  onSelect?: (key: string, value: string) => void;
}) {
  const isSwatch = hasSwatchImages(item);
  const canSelect = item.selectable && !!onSelect;

  return (
    <div className="mb-4">
      <div className="mb-1.5 text-xs font-semibold text-gray-600">{item.key}</div>
      {isSwatch ? (
        <div className="flex flex-wrap gap-2">
          {item.values.map((v, i) => {
            const isSelected = canSelect && selectedValue === v.value;
            const swatchOk = v.value_type === "image" && v.swatch_image;
            return (
              <button
                key={i}
                type="button"
                disabled={!canSelect}
                onClick={() => canSelect && onSelect(item.key, v.value)}
                className={`relative rounded-md border-2 transition-colors ${
                  isSelected
                    ? "border-[#0D4D4D] ring-1 ring-[#0D4D4D]/30"
                    : "border-transparent hover:border-gray-300"
                } ${canSelect ? "cursor-pointer" : "cursor-default"}`}
              >
                {swatchOk ? (
                  <SwatchThumb src={v.swatch_image!} alt={v.value} />
                ) : (
                  <div className="flex h-[54px] w-[54px] items-center justify-center rounded-md border border-gray-200 bg-gray-50 text-xs text-gray-600">
                    {v.value}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {item.values.map((v, i) => {
            const isSelected = canSelect && selectedValue === v.value;
            return (
              <button
                key={i}
                type="button"
                disabled={!canSelect}
                onClick={() => canSelect && onSelect(item.key, v.value)}
                className={`rounded-md border-[1.5px] px-3.5 py-1.5 text-xs transition-colors ${
                  isSelected
                    ? "border-[#0D4D4D] bg-[#e6f3f3] text-[#0D4D4D] font-medium"
                    : "border-gray-200 bg-white text-gray-600"
                } ${canSelect ? "cursor-pointer hover:border-gray-400" : "cursor-default"}`}
              >
                {v.value}
                {item.unit ? ` ${item.unit}` : ""}
              </button>
            );
          })}
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
    <div className="mt-6">
      <h4 className="mb-3 text-sm font-semibold text-gray-700">{t("detail.productDetail")}</h4>
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

  // 锚点导航:Tab 点击滚动到对应区域,滚动时高亮联动
  const [activeTab, setActiveTab] = useState<TabKey>("specifications");
  const sectionRefs = useRef<Record<TabKey, HTMLDivElement | null>>({
    specifications: null,
    description: null,
    gallery: null,
  });

  const scrollToSection = useCallback((key: TabKey) => {
    const el = sectionRefs.current[key];
    if (el) {
      // 偏移量:留出 tab 栏高度
      const offset = 60;
      const top = el.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: "smooth" });
    }
  }, []);

  // 滚动监听:距离视口顶部最近的 section 高亮
  useEffect(() => {
    const handleScroll = () => {
      const keys: TabKey[] = ["specifications", "description", "gallery"];
      let closest: TabKey = "specifications";
      let minDist = Infinity;
      for (const key of keys) {
        const el = sectionRefs.current[key];
        if (!el) continue;
        const dist = Math.abs(el.getBoundingClientRect().top - 80);
        if (dist < minDist) {
          minDist = dist;
          closest = key;
        }
      }
      setActiveTab(closest);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // 规格选中态:仅前端本地,刷新即重置
  const [specSelection, setSpecSelection] = useState<Record<string, string>>({});

  // 点选/取消规格值(单选:每个 key 选一个值)
  const handleSpecSelect = useCallback((key: string, value: string) => {
    setSpecSelection((prev) => {
      if (prev[key] === value) {
        // 取消选中
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  }, []);

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

            {/* 基础信息(产地/品牌/MOQ) */}
            {(product.origin || product.brand || product.moq != null) && (
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
                {product.moq != null && (
                  <span>{t("detail.moq")}: <span className="font-medium text-gray-700">{product.moq.toLocaleString()} {product.moq_unit || product.unit || ""}</span></span>
                )}
                {product.origin && (
                  <span>{t("detail.origin")}: <span className="font-medium text-gray-700">{product.origin}</span></span>
                )}
                {product.brand && (
                  <span>{t("detail.brand")}: <span className="font-medium text-gray-700">{product.brand}</span></span>
                )}
              </div>
            )}

            {/* 属性:颜色色板 / 厚度 chip(多值项);selectable=true 可点选 */}
            {inlineAttrs.length > 0 && (
              <div className="mt-4">
                {inlineAttrs.map((item) => (
                  <InlineAttrItem
                    key={item.key}
                    item={item}
                    selectedValue={specSelection[item.key]}
                    onSelect={handleSpecSelect}
                  />
                ))}
              </div>
            )}

            {/* 操作按钮 — 出口仍置灰,选中态仅前端本地,不发请求、不带出 */}
            <div className="mt-4 flex flex-wrap gap-2.5">
              {/* TODO: ① 带入询价:询价行粒度(SPU vs Product+selected_specs)定调后(张总/温总),把本地 specSelection 接到询价提交 */}
              {/* TODO: ② SKU 轴去重汇总:手工建带 SKU 商品的规格轴,后端去重汇总后也纳入可选(需后端增量) */}
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

      {/* ===== Tab 锚点导航(阿里风格:点击滚动,滚动联动高亮) ===== */}
      <div className="sticky top-0 z-20 mt-4 rounded-t-xl border border-gray-200 bg-white">
        <div className="flex border-b border-gray-200">
          {tabItems.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => scrollToSection(tab.key)}
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
      </div>

      {/* ===== 内容平铺(所有 section 展开) ===== */}
      <div className="rounded-b-xl border border-t-0 border-gray-200 bg-white">
        {/* 产品规格 */}
        <div ref={(el) => { sectionRefs.current.specifications = el; }} className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{t("detail.tabSpecs")}</h3>
          <SpecificationsTab product={product} />
        </div>

        <hr className="border-gray-100" />

        {/* 产品描述 */}
        <div ref={(el) => { sectionRefs.current.description = el; }} className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{t("detail.tabDescription")}</h3>
          <DescriptionTab product={product} />
        </div>

        <hr className="border-gray-100" />

        {/* 产品图片 */}
        <div ref={(el) => { sectionRefs.current.gallery = el; }} className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{t("detail.tabGallery")}</h3>
          <GalleryTab product={product} />
          {/* 商品详情大图(平铺在图片 section 内) */}
          <ProductDetailImages product={product} />
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
