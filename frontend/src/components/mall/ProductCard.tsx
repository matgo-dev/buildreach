"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { Package, ShoppingCart, Loader2 } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { addCartItem } from "@/lib/api/cart";
import { useToast } from "@/components/ui/Toast";
import { useCartStore } from "@/stores/cartStore";
import { useAuthStore } from "@/stores/authStore";
import { MallButton } from "./MallButton";
import { imageUrl } from "@/lib/env";

/** 飞入购物车动画：暖金流星效果 */
function flyToCart(startEl: HTMLElement) {
  const target = document.querySelector("[data-cart-icon]") as HTMLElement | null;
  if (!target) return;

  const startRect = startEl.getBoundingClientRect();
  const endRect = target.getBoundingClientRect();

  const sx = startRect.left + startRect.width / 2;
  const sy = startRect.top + startRect.height / 2;
  const ex = endRect.left + endRect.width / 2;
  const ey = endRect.top + endRect.height / 2;
  const angle = Math.atan2(ey - sy, ex - sx) * (180 / Math.PI);

  const meteor = document.createElement("div");
  meteor.style.cssText = `
    position: fixed;
    z-index: 99999;
    left: ${sx}px;
    top: ${sy}px;
    width: 36px;
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, transparent 0%, #e3a615 40%, #f0c040 100%);
    box-shadow: 0 0 8px rgba(227, 166, 21, 0.6), 0 0 16px rgba(227, 166, 21, 0.3);
    pointer-events: none;
    transform: rotate(${angle}deg);
    transform-origin: right center;
    opacity: 0;
    transition: left 1s cubic-bezier(0.25, 0.1, 0.25, 1),
                top 1s cubic-bezier(0.25, 0.1, 0.25, 1),
                opacity 0.3s ease,
                width 0.8s ease;
  `;
  document.body.appendChild(meteor);

  requestAnimationFrame(() => {
    meteor.style.opacity = "1";
    requestAnimationFrame(() => {
      meteor.style.left = `${ex}px`;
      meteor.style.top = `${ey}px`;
      meteor.style.width = "12px";
      setTimeout(() => { meteor.style.opacity = "0"; }, 600);
    });
  });

  setTimeout(() => {
    meteor.remove();
    target.style.transition = "transform 0.3s ease";
    target.style.transform = "scale(1.3)";
    setTimeout(() => { target.style.transform = "scale(1)"; }, 300);
  }, 1050);
}

/** 从品类树中按 code 查找品类名称 */
function findCategoryLabel(tree: CategoryTreeNode[], code: string): string {
  for (const l1 of tree) {
    if (l1.code === code) return l1.name;
    for (const l2 of l1.children || []) {
      if (l2.code === code) return l2.name;
      for (const l3 of l2.children || []) {
        if (l3.code === code) return l3.name;
      }
    }
  }
  return "";
}

/**
 * 商品卡片 — 深青信任风格。
 */
export function ProductCard({
  product,
  categoryTree,
  href,
}: {
  product: ProductPublic;
  categoryTree: CategoryTreeNode[];
  /** 详情页链接,默认 `/mall/products/{id}`;专区等场景需覆盖为各自的详情路由 */
  href?: string;
}) {
  const t = useTranslations("mall");
  const categoryLabel = findCategoryLabel(categoryTree, product.category_code);
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const toast = useToast();
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const btnRef = useRef<HTMLButtonElement>(null);

  const prevCountRef = useRef(useCartStore.getState().count);
  const handleAddToCart = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // 未登录 → 跳登录页
    if (!useAuthStore.getState().user) {
      router.push("/login");
      return;
    }
    setAdding(true);
    prevCountRef.current = useCartStore.getState().count;
    try {
      const cart = await addCartItem(product.id, [], 1);
      syncFromCart(cart);
      const newCount = cart.items.filter((i) => i.is_purchasable).length;
      if (newCount > prevCountRef.current) {
        // 新增行 → 飞入动画
        if (btnRef.current) flyToCart(btnRef.current);
        toast.success(t("addedToCart"));
      } else {
        // 累加数量 → toast 提示
        toast.success(t("alreadyInCart"));
      }
    } catch {
      toast.error(t("addToCartFailed"));
    } finally {
      setAdding(false);
    }
  }, [product.id, syncFromCart, toast, t]);

  return (
    <Link
      href={href ?? `/mall/products/${product.id}`}
      className="group block rounded-xl border border-line bg-white overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-teal-700 hover:shadow-mall-md shadow-mall-sm"
    >
      {/* 图片区 — 撑满，窄边距 */}
      <div
        className="relative aspect-square flex items-center justify-center overflow-hidden border-b border-[#edf2f5] p-2"
        style={{ background: "linear-gradient(135deg, #f0faf9, #fff)" }}
      >
        {product.main_image ? (
          <img
            src={imageUrl(product.main_image_thumbnail || product.main_image)}
            onError={(e) => {
              const t = e.currentTarget;
              if (t.dataset.fallback) return;
              t.dataset.fallback = "1";
              t.src = imageUrl(product.main_image!);
            }}
            alt={product.name}
            width={300}
            height={300}
            className="h-full w-full object-contain"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <Package className="h-12 w-12 text-gray-300" />
        )}
      </div>

      {/* 信息区 */}
      <div className="p-2.5 sm:p-3.5 space-y-1.5 sm:space-y-2">
        <h3 className="min-h-[40px] sm:min-h-[46px] text-[13px] sm:text-[14.5px] font-extrabold leading-tight text-navy line-clamp-2 group-hover:text-teal-900">
          {product.supply_mode === "PLATFORM_STOCK" ? (
            <span className="inline-flex items-center rounded bg-teal-900 px-1.5 py-px text-[10px] font-bold text-white mr-1 align-text-top">
              {t("supplyModePlatformStock")}
            </span>
          ) : (
            <span className="inline-flex items-center rounded border border-teal-700 px-1.5 py-px text-[10px] font-bold text-teal-800 mr-1 align-text-top">
              {t("supplyModeSupplierDirect")}
            </span>
          )}
          {product.name}
        </h3>

        {product.description && (
          <p className="text-xs text-muted leading-relaxed line-clamp-2">
            {product.description}
          </p>
        )}

        <div className="flex flex-wrap gap-1.5">
          {categoryLabel && (
            <span className="inline-flex items-center rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-extrabold text-teal-900 whitespace-nowrap">
              {categoryLabel}
            </span>
          )}
          {product.certifications?.map((cert) => (
            <span
              key={cert}
              className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-extrabold whitespace-nowrap"
              style={{ color: "#15935f", background: "#e5f7ee" }}
            >
              {cert}
            </span>
          ))}
        </div>

        {product.moq != null && (
          <p className="text-xs text-muted">
            <span className="font-extrabold text-navy">MOQ:</span>{" "}
            {product.moq.toLocaleString()} {product.moq_unit || product.unit || ""}
          </p>
        )}

        {/* 底部操作 */}
        <div className="flex gap-2 pt-1">
          <MallButton
            variant="teal"
            size="md"
            className="text-[13px] min-w-0 flex-1"
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              router.push(`/buyer/rfqs/create?product_id=${product.id}`);
            }}
          >
            {t("startInquiry")}
          </MallButton>
          <button
            ref={btnRef}
            type="button"
            onClick={handleAddToCart}
            disabled={adding}
            className="h-10 w-10 shrink-0 rounded-md border-[1.5px] border-line-strong bg-white grid place-items-center text-teal-900 hover:bg-teal-50 hover:border-teal-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t("addToInquiryCart")}
          >
            {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShoppingCart className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </Link>
  );
}
