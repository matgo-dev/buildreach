"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Package } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";

interface Props {
  product: ProductPublic;
  categoryTree: CategoryTreeNode[];
}

/** 从品类树中按 code 查找品类名称（遍历到 L2 即可） */
function findCategoryLabel(
  tree: CategoryTreeNode[],
  code: string
): string {
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

export function ProductCard({ product, categoryTree }: Props) {
  const t = useTranslations("mall");
  const categoryLabel = findCategoryLabel(categoryTree, product.category_code);

  return (
    <Link
      href={`/mall/products/${product.id}`}
      className="group block rounded-lg border border-gray-200 bg-white overflow-hidden transition-shadow hover:shadow-md"
    >
      {/* 图片区 */}
      <div className="relative aspect-[4/3] bg-gray-50 flex items-center justify-center overflow-hidden">
        {product.main_image ? (
          <img
            src={product.main_image}
            alt={product.name}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <Package className="h-12 w-12 text-gray-300" />
        )}
        {product.is_featured && (
          <span className="absolute top-2 right-2 rounded bg-[#FF6B35] px-2 py-0.5 text-[10px] font-semibold text-white">
            {t("featured")}
          </span>
        )}
      </div>

      {/* 信息区 */}
      <div className="p-3">
        {/* 品类 */}
        {categoryLabel && (
          <p className="mb-1 truncate text-[11px] font-medium text-[#0D4D4D]">
            {categoryLabel}
          </p>
        )}

        {/* 商品名 */}
        <h3 className="mb-1.5 line-clamp-2 text-sm font-semibold leading-snug text-gray-900 group-hover:text-[#0D4D4D]">
          {product.name}
        </h3>

        {/* 认证 */}
        {product.certifications && product.certifications.length > 0 && (
          <div className="mb-1.5 flex flex-wrap gap-1">
            {product.certifications.map((cert) => (
              <span
                key={cert}
                className="rounded bg-green-50 px-1.5 py-0.5 text-[10px] font-semibold text-green-700"
              >
                {cert}
              </span>
            ))}
          </div>
        )}

        {/* MOQ */}
        {product.moq != null && (
          <p className="text-xs text-gray-500">
            <span className="font-medium text-gray-700">MOQ:</span>{" "}
            {product.moq.toLocaleString()} {product.moq_unit || product.unit || ""}
          </p>
        )}
      </div>
    </Link>
  );
}
