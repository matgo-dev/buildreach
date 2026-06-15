"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Package, ShoppingCart, Loader2 } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { addCartItem } from "@/lib/api/cart";
import { useToast } from "@/components/ui/Toast";
import { useCartStore } from "@/stores/cartStore";
import { MallButton } from "./MallButton";

/** 飞入购物车动画：带尾巴的流星效果，渐出渐入 */
function flyToCart(startEl: HTMLElement) {
  const target = document.querySelector("[data-cart-icon]") as HTMLElement | null;
  if (!target) return;

  const startRect = startEl.getBoundingClientRect();
  const endRect = target.getBoundingClientRect();

  const sx = startRect.left + startRect.width / 2;
  const sy = startRect.top + startRect.height / 2;
  const ex = endRect.left + endRect.width / 2;
  const ey = endRect.top + endRect.height / 2;

  // 计算角度，让尾巴朝运动反方向
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
    background: linear-gradient(90deg, transparent 0%, #0D4D4D 40%, #1A6B6B 100%);
    box-shadow: 0 0 8px rgba(13, 77, 77, 0.5), 0 0 16px rgba(13, 77, 77, 0.2);
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

  // 渐入
  requestAnimationFrame(() => {
    meteor.style.opacity = "1";
    requestAnimationFrame(() => {
      meteor.style.left = `${ex}px`;
      meteor.style.top = `${ey}px`;
      meteor.style.width = "12px";
      // 飞行后半段渐出
      setTimeout(() => { meteor.style.opacity = "0"; }, 600);
    });
  });

  setTimeout(() => {
    meteor.remove();
    // 购物车图标弹跳
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
}: {
  product: ProductPublic;
  categoryTree: CategoryTreeNode[];
}) {
  const t = useTranslations("mall");
  const categoryLabel = findCategoryLabel(categoryTree, product.category_code);
  const [adding, setAdding] = useState(false);
  const toast = useToast();
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const btnRef = useRef<HTMLButtonElement>(null);

  const handleAddToCart = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setAdding(true);
    try {
      const cart = await addCartItem(product.id, [], 1);
      syncFromCart(cart);
      if (btnRef.current) flyToCart(btnRef.current);
    } catch {
      toast.error(t("addToCartFailed"));
    } finally {
      setAdding(false);
    }
  }, [product.id, syncFromCart, toast, t]);

  return (
    <Link
      href={`/mall/products/${product.id}`}
      className="group block rounded-xl border border-line bg-white overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-teal-700 hover:shadow-mall-md shadow-mall-sm"
    >
      {/* 图片区 */}
      <div
        className="relative min-h-[152px] flex items-center justify-center overflow-hidden border-b border-[#edf2f5]"
        style={{ background: "linear-gradient(135deg, #f0faf9, #fff)" }}
      >
        {product.main_image ? (
          <img
            src={product.main_image}
            alt={product.name}
            className="h-[142px] w-[142px] object-contain mix-blend-multiply"
            loading="lazy"
          />
        ) : (
          <Package className="h-12 w-12 text-gray-300" />
        )}
        <div className="absolute top-2.5 left-2.5 flex gap-1">
          {product.is_featured && (
            <span className="rounded-full bg-whatsapp px-2.5 py-0.5 text-[11px] font-extrabold text-white">
              {t("featured")}
            </span>
          )}
          {product.supply_mode === "PLATFORM_STOCK" ? (
            <span className="rounded-full bg-blue-600 px-2.5 py-0.5 text-[11px] font-extrabold text-white">
              {t("supplyModePlatformStock")}
            </span>
          ) : (
            <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-[11px] font-extrabold text-white">
              {t("supplyModeSupplierDirect")}
            </span>
          )}
        </div>
      </div>

      {/* 信息区 */}
      <div className="p-3.5 space-y-2">
        <h3 className="min-h-[46px] text-[14.5px] font-extrabold leading-tight text-navy line-clamp-2 group-hover:text-teal-900">
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
        <div className="grid grid-cols-[1fr_40px] gap-2 pt-1">
          <MallButton variant="teal" size="md" className="text-[13px]">
            {t("startInquiry")}
          </MallButton>
          <button
            ref={btnRef}
            type="button"
            onClick={handleAddToCart}
            disabled={adding}
            className="h-10 w-10 rounded-md border-[1.5px] border-line-strong bg-white grid place-items-center text-teal-900 hover:bg-teal-50 hover:border-teal-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t("addToInquiryCart")}
          >
            {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShoppingCart className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </Link>
  );
}
