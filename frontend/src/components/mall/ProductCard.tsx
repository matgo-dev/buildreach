"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Package } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { formatCurrency } from "@/lib/formatters";

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

/** 格式化交期 */
function formatLeadTime(min: number | null, max: number | null): string {
  if (min == null && max == null) return "";
  if (min != null && max != null && min !== max) return `${min}-${max}d`;
  const val = min ?? max;
  return `${val}d`;
}

export function ProductCard({ product, categoryTree }: Props) {
  const locale = useLocale();
  const t = useTranslations("mall");
  const categoryLabel = findCategoryLabel(categoryTree, product.category_code);

  const priceDisplay = (() => {
    if (product.price_min == null) return t("noPrice");
    const currency = product.currency || "TZS";
    const min = formatCurrency(product.price_min, currency, locale, { maximumFractionDigits: 0 });
    if (product.price_max != null && product.price_max !== product.price_min) {
      const max = formatCurrency(product.price_max, currency, locale, { maximumFractionDigits: 0 });
      return `${min} ~ ${max}`;
    }
    return min;
  })();

  // mall namespace 有 unit_PCS / unit_SET 等 key
  const unitKey = product.unit ? `unit_${product.unit}` : null;
  let unitLabel = "";
  if (unitKey) {
    try { unitLabel = t(unitKey as any); } catch { unitLabel = product.unit || ""; }
  }
  const leadTime = formatLeadTime(product.lead_time_min, product.lead_time_max);

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

        {/* 价格 */}
        <p className="text-base font-bold text-[#0D4D4D]">
          {priceDisplay}
          {unitLabel && (
            <span className="ml-0.5 text-xs font-normal text-gray-400">
              / {unitLabel}
            </span>
          )}
        </p>

        {/* MOQ + 交期 */}
        <p className="mt-1 text-[11px] text-gray-400">
          {product.moq != null && (
            <span>MOQ: {product.moq} {unitLabel}</span>
          )}
          {product.moq != null && leadTime && <span> · </span>}
          {leadTime && <span>{leadTime}</span>}
        </p>

        {/* 多 SKU 提示 */}
        {product.sku_count > 1 && (
          <p className="mt-1 text-[11px] font-medium text-[#0D4D4D]">
            {t("variants", { count: product.sku_count })}
          </p>
        )}
      </div>
    </Link>
  );
}
