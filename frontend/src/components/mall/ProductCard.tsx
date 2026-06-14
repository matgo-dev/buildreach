"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Package, ShoppingCart } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";

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
 * 商品卡片 — 深青信任风格。参考 HTML .product-card
 *
 * 图片区 teal-50 渐变底 + hover 上浮 + 分层阴影
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

  return (
    <Link
      href={`/mall/products/${product.id}`}
      className="group block rounded-xl border border-line bg-white overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-teal-700 hover:shadow-mall-md"
      style={{ boxShadow: "0 1px 2px rgba(16,36,65,.05), 0 2px 6px rgba(16,36,65,.04)" }}
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
        {product.is_featured && (
          <span className="absolute top-2.5 left-2.5 rounded-full bg-whatsapp px-2.5 py-0.5 text-[11px] font-extrabold text-white">
            {t("featured")}
          </span>
        )}
      </div>

      {/* 信息区 */}
      <div className="p-3.5 space-y-2">
        {/* 商品名 */}
        <h3 className="min-h-[46px] text-[14.5px] font-extrabold leading-tight text-navy line-clamp-2 group-hover:text-teal-900">
          {product.name}
        </h3>

        {/* 标签行:品类 + 认证 */}
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

        {/* MOQ */}
        {product.moq != null && (
          <p className="text-xs text-muted">
            <span className="font-extrabold text-navy">MOQ:</span>{" "}
            {product.moq.toLocaleString()} {product.moq_unit || product.unit || ""}
          </p>
        )}

        {/* 底部操作 */}
        <div className="grid grid-cols-[1fr_40px] gap-2 pt-1">
          <span
            className="h-10 rounded-[10px] flex items-center justify-center text-white text-[13px] font-extrabold transition-all"
            style={{
              background: "linear-gradient(135deg, #07808b, #00505a, #003f46)",
              boxShadow: "0 6px 16px rgba(0,63,70,.22)",
            }}
          >
            {t("startInquiry")}
          </span>
          <span
            className="h-10 w-10 rounded-md border-[1.5px] border-line-strong bg-white grid place-items-center text-teal-900 hover:bg-teal-50 hover:border-teal-800 transition-colors"
            title={t("addToInquiryCart")}
          >
            <ShoppingCart className="h-4 w-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}
