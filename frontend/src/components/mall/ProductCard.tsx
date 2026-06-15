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

/** 飞入购物车动画：从按钮位置飞向右上角购物车图标 */
function flyToCart(startEl: HTMLElement) {
  // 找到 header 里的购物车图标
  const target = document.querySelector("[data-cart-icon]") as HTMLElement | null;
  if (!target) return;

  const startRect = startEl.getBoundingClientRect();
  const endRect = target.getBoundingClientRect();

  const dot = document.createElement("div");
  dot.style.cssText = `
    position: fixed;
    z-index: 99999;
    left: ${startRect.left + startRect.width / 2}px;
    top: ${startRect.top + startRect.height / 2}px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #0D4D4D;
    pointer-events: none;
    transition: all 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);
    opacity: 1;
  `;
  document.body.appendChild(dot);

  requestAnimationFrame(() => {
    dot.style.left = `${endRect.left + endRect.width / 2}px`;
    dot.style.top = `${endRect.top + endRect.height / 2}px`;
    dot.style.width = "8px";
    dot.style.height = "8px";
    dot.style.opacity = "0.3";
  });

  setTimeout(() => {
    dot.remove();
    // 购物车图标弹跳效果
    target.classList.add("animate-bounce");
    setTimeout(() => target.classList.remove("animate-bounce"), 500);
  }, 650);
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
