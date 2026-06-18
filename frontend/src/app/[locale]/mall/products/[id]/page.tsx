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
  X,
} from "lucide-react";
import Link from "next/link";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { getProduct, type ProductPublicDetail, type AttrGroup, type AttrItem } from "@/lib/api/products";
import { addCartItem } from "@/lib/api/cart";
import { useToast } from "@/components/ui/Toast";
import { useCartStore } from "@/stores/cartStore";
import { ProductGallery } from "@/components/mall/ProductGallery";
import { useWhatsApp } from "@/hooks/useWhatsApp";

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

// ---- 色板缩略图（点击可放大预览） ----

function SwatchThumb({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  const [preview, setPreview] = useState(false);

  if (failed) {
    return (
      <div className="flex h-[54px] w-[54px] items-center justify-center rounded-md border border-gray-200 bg-gray-50 text-xs text-gray-500">
        {alt || "—"}
      </div>
    );
  }

  return (
    <>
      <div
        className="relative"
        onDoubleClick={(e) => { e.stopPropagation(); setPreview(true); }}
      >
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
      {/* 色板放大预览 */}
      {preview && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70"
          onClick={() => setPreview(false)}
        >
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={alt}
              className="max-h-[70vh] max-w-[70vw] rounded-lg object-contain"
            />
            <button
              onClick={() => setPreview(false)}
              className="absolute -right-3 -top-3 rounded-full bg-white p-1.5 shadow-md hover:bg-gray-100 transition-colors"
            >
              <X className="h-4 w-4 text-gray-600" />
            </button>
            {alt && (
              <p className="mt-2 text-center text-sm text-white/80">{alt}</p>
            )}
          </div>
        </div>
      )}
    </>
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
                    ? "border-[#00505a] ring-1 ring-[#00505a]/30"
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
                    ? "border-[#00505a] bg-[#e6f3f3] text-[#00505a] font-medium"
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

type TabKey = "specifications" | "description";

function SpecificationsTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  const baseRows: { label: string; value: string }[] = [];
  if (product.origin) baseRows.push({ label: t("detail.origin"), value: product.origin });
  if (product.brand) baseRows.push({ label: t("detail.brand"), value: product.brand });
  if (product.hs_code) baseRows.push({ label: t("detail.hsCode"), value: product.hs_code });

  const groups = product.attribute_groups;

  // 把属性组的 items 打平成 { label, value } 列表,按组分段
  type SpecSection = { groupLabel: string; rows: { label: string; value: string }[] };
  const sections: SpecSection[] = [];

  // 基础属性作为第一段(无分组标题)
  if (baseRows.length > 0) {
    sections.push({ groupLabel: "", rows: baseRows });
  }

  for (const group of groups) {
    const groupKey = `detail.attrGroup_${group.group}` as Parameters<typeof t>[0];
    let groupLabel: string;
    try { groupLabel = t(groupKey); } catch { groupLabel = group.group; }
    if (groupLabel === groupKey || groupLabel.includes("attrGroup_")) groupLabel = group.group;

    const rows = group.items.map((item) => ({
      label: item.key,
      value: item.values.map((v) => v.value).join(", ") + (item.unit ? ` ${item.unit}` : ""),
    }));
    if (rows.length > 0) {
      sections.push({ groupLabel, rows });
    }
  }

  // 每行放两组 key-value（4 列布局）
  const renderPairedRows = (rows: { label: string; value: string }[]) => {
    const paired: React.ReactNode[] = [];
    for (let i = 0; i < rows.length; i += 2) {
      const left = rows[i];
      const right = rows[i + 1];
      paired.push(
        <tr key={i} className={i % 4 === 0 ? "bg-white" : "bg-gray-50/40"}>
          <td className="border border-gray-200 px-4 py-2.5 text-gray-500 whitespace-nowrap">{left.label}</td>
          <td className="border border-gray-200 px-4 py-2.5 text-gray-800">{left.value}</td>
          {right ? (
            <>
              <td className="border border-gray-200 px-4 py-2.5 text-gray-500 whitespace-nowrap">{right.label}</td>
              <td className="border border-gray-200 px-4 py-2.5 text-gray-800">{right.value}</td>
            </>
          ) : (
            <>
              <td className="border border-gray-200 px-4 py-2.5" />
              <td className="border border-gray-200 px-4 py-2.5" />
            </>
          )}
        </tr>
      );
    }
    return paired;
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[18%]" />
          <col className="w-[32%]" />
          <col className="w-[18%]" />
          <col className="w-[32%]" />
        </colgroup>
        <tbody>
          {sections.map((section, si) => (
            <React.Fragment key={si}>
              {section.groupLabel && (
                <tr>
                  <td
                    colSpan={4}
                    className="border border-gray-200 bg-gray-50 px-4 py-2 text-sm font-bold text-gray-700"
                  >
                    {section.groupLabel}
                  </td>
                </tr>
              )}
              {renderPairedRows(section.rows)}
            </React.Fragment>
          ))}
        </tbody>
      </table>
      {sections.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">{t("detail.noSpecs")}</p>
      )}
    </div>
  );
}

// ---- Tab: 产品描述 ----

function DescriptionTab({ product }: { product: ProductPublicDetail }) {
  const t = useTranslations("mall");

  // 所有 SPU 级图片平铺在描述区
  const detailImages = product.images
    .filter((img) => img.sku_id == null)
    .sort((a, b) => a.sort_order - b.sort_order);

  // detail_description 存在时,卖点/短描述已在顶部面板展示过,Tab 里不再重复
  const hasDetailDesc = !!product.detail_description;
  const hasText = !!(product.description || product.selling_points || product.detail_description);

  return (
    <div className="space-y-6">
      {!hasDetailDesc && product.selling_points && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">{t("detail.sellingPoints")}</h4>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
            {product.selling_points}
          </div>
        </div>
      )}
      {!hasDetailDesc && product.description && (
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
          {product.description}
        </div>
      )}
      {/* 产品介绍长文:在详情图之前 */}
      {product.detail_description && (
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
          {product.detail_description}
        </div>
      )}
      {/* DETAIL 描述长图 */}
      {detailImages.length > 0 && (
        <div className="mx-auto max-w-3xl space-y-4">
          {detailImages.map((img) => (
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
      )}
      {!hasText && detailImages.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">{t("detail.noDescription")}</p>
      )}
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
  });

  const scrollToSection = useCallback((key: TabKey) => {
    const el = sectionRefs.current[key];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    // 立即更新 Tab 高亮,不等滚动监听
    setActiveTab(key);
  }, []);

  // 滚动监听:距离视口顶部最近的 section 高亮
  useEffect(() => {
    const handleScroll = () => {
      const keys: TabKey[] = ["specifications", "description"];
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
  const [addingToCart, setAddingToCart] = useState(false);
  const toast = useToast();
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const wa = useWhatsApp();
  const addBtnRef = useRef<HTMLButtonElement>(null);

  const prevCountRef = useRef(0);
  const handleAddToCart = useCallback(async () => {
    if (!product) return;
    setAddingToCart(true);
    prevCountRef.current = useCartStore.getState().count;
    try {
      const selectedVariants = Object.entries(specSelection)
        .filter(([, v]) => v)
        .map(([attr_name, value]) => ({ attr_name, value }));
      const cart = await addCartItem(product.id, selectedVariants, 1);
      syncFromCart(cart);
      const newCount = cart.items.filter((i) => i.is_purchasable).length;
      if (newCount > prevCountRef.current) {
        // 新增行 → 飞入动画
        if (addBtnRef.current) {
          const target = document.querySelector("[data-cart-icon]") as HTMLElement | null;
          if (target) {
            const sr = addBtnRef.current.getBoundingClientRect();
            const er = target.getBoundingClientRect();
            const sx = sr.left + sr.width / 2, sy = sr.top + sr.height / 2;
            const ex = er.left + er.width / 2, ey = er.top + er.height / 2;
            const angle = Math.atan2(ey - sy, ex - sx) * (180 / Math.PI);
            const m = document.createElement("div");
            m.style.cssText = `position:fixed;z-index:99999;left:${sx}px;top:${sy}px;width:36px;height:6px;border-radius:3px;background:linear-gradient(90deg,transparent 0%,#e3a615 40%,#f0c040 100%);box-shadow:0 0 8px rgba(227,166,21,0.6),0 0 16px rgba(227,166,21,0.3);pointer-events:none;transform:rotate(${angle}deg);transform-origin:right center;opacity:0;transition:left 1s cubic-bezier(0.25,0.1,0.25,1),top 1s cubic-bezier(0.25,0.1,0.25,1),opacity 0.3s ease,width 0.8s ease;`;
            document.body.appendChild(m);
            requestAnimationFrame(() => { m.style.opacity = "1"; requestAnimationFrame(() => { m.style.left = `${ex}px`; m.style.top = `${ey}px`; m.style.width = "12px"; setTimeout(() => { m.style.opacity = "0"; }, 600); }); });
            setTimeout(() => { m.remove(); target.style.transition = "transform 0.3s ease"; target.style.transform = "scale(1.3)"; setTimeout(() => { target.style.transform = "scale(1)"; }, 300); }, 1050);
          }
        }
        toast.success(t("detail.addedToCart"));
      } else {
        toast.success(t("detail.alreadyInCart"));
      }
    } catch {
      toast.error(t("detail.addToCartFailed"));
    } finally {
      setAddingToCart(false);
    }
  }, [product, specSelection, syncFromCart, toast, t]);

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

  // Gallery 图片列表（稳定引用，避免每次渲染 filter 产生新数组导致主图重置）
  const galleryImages = useMemo(() => {
    if (!product) return [];
    return product.images.filter((img) => img.sku_id == null && img.image_type !== "DETAIL");
  }, [product]);

  // 可选规格轴提到右侧面板(颜色/厚度等)
  const inlineAttrs = useMemo(() => {
    if (!product) return [];
    const items: AttrItem[] = [];
    for (const group of product.attribute_groups) {
      for (const item of group.items) {
        if (item.selectable && item.values.length > 0) {
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
            <Loader2 className="h-8 w-8 animate-spin text-[#00505a]" />
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
                className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-[#00505a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d]"
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
          className="flex items-center gap-1 text-[#00505a] transition-colors hover:underline"
        >
          <Home className="h-3 w-3" />
          Home
        </Link>
        {breadcrumb.map((crumb) => (
          <React.Fragment key={crumb.code}>
            <ChevronRight className="h-3 w-3" />
            <Link
              href={`/${locale}/mall?cat=${crumb.code}`}
              className="text-[#00505a] transition-colors hover:underline"
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
            images={galleryImages}
          />

          {/* 右:信息面板 */}
          <div className="min-w-0 flex-1">
            <p className="text-[11px] text-gray-400">SPU: {product.spu_code}</p>
            <h1 className="text-xl font-bold text-gray-800">{product.name}</h1>

            {/* 认证徽章行（与列表卡片统一，不再显示履约模式/精选标签） */}

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
              <div className="mt-3 rounded-lg border border-[#00505a]/10 bg-[#00505a]/[0.03] px-4 py-3">
                {product.selling_points && (
                  <div className="text-sm leading-relaxed text-gray-800">
                    <span className="mr-1.5 text-xs font-semibold text-[#00505a]">✦ {t("detail.sellingPoints")}</span>
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

            {/* 属性:颜色色板 / 厚度 chip;仅展示 selectable=true 的可选规格轴 */}
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
              <button
                ref={addBtnRef}
                type="button"
                disabled={addingToCart}
                onClick={handleAddToCart}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#00505a] px-6 py-3 text-sm font-semibold text-white hover:bg-[#003d45] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addingToCart ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShoppingCart className="h-4 w-4" />}
                {t("detail.addToInquiry")}
              </button>
              {wa.configured && (
              <a
                href={wa.link!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#25D366] px-6 py-3 text-sm font-semibold text-white hover:bg-[#20bd5a] transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                WhatsApp {t("detail.contactPlatform")}
              </a>
              )}
            </div>
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
                  ? "border-b-2 border-[#00505a] text-[#00505a]"
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
        <div ref={(el) => { sectionRefs.current.specifications = el; }} className="scroll-mt-14 p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{t("detail.tabSpecs")}</h3>
          <SpecificationsTab product={product} />
        </div>

        <hr className="border-gray-100" />

        {/* 产品描述(文字 + DETAIL 描述长图合并) */}
        <div ref={(el) => { sectionRefs.current.description = el; }} className="scroll-mt-14 p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-800">{t("detail.tabDescription")}</h3>
          <DescriptionTab product={product} />
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
