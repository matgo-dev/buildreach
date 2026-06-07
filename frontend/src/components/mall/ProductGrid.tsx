"use client";

import { useTranslations } from "next-intl";
import { Search, AlertCircle, RefreshCw } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { ProductCard } from "./ProductCard";

interface Props {
  products: ProductPublic[];
  categoryTree: CategoryTreeNode[];
  isLoading: boolean;
  error: Error | undefined;
  onRetry: () => void;
  onClearFilters: () => void;
}

/** 骨架屏卡片 */
function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="aspect-[4/3] bg-gray-100" />
      <div className="p-3 space-y-2">
        <div className="h-3 w-16 rounded bg-gray-100" />
        <div className="h-4 w-full rounded bg-gray-100" />
        <div className="h-3 w-24 rounded bg-gray-100" />
        <div className="h-5 w-20 rounded bg-gray-100" />
        <div className="h-3 w-28 rounded bg-gray-100" />
      </div>
    </div>
  );
}

export function ProductGrid({
  products,
  categoryTree,
  isLoading,
  error,
  onRetry,
  onClearFilters,
}: Props) {
  const t = useTranslations("mall");

  // 加载中
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  // 错误
  if (error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white py-20 text-center">
        <AlertCircle className="mx-auto mb-3 h-10 w-10 text-red-300" />
        <p className="text-sm font-medium text-gray-600">{t("loadError")}</p>
        <button
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#0D4D4D] px-4 py-2 text-xs font-medium text-white hover:bg-[#0a3d3d] transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {t("retry")}
        </button>
      </div>
    );
  }

  // 无结果
  if (products.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white py-20 text-center">
        <Search className="mx-auto mb-3 h-10 w-10 text-gray-300" />
        <p className="text-sm font-medium text-gray-600">{t("noProducts")}</p>
        <p className="mt-1 text-xs text-gray-400">{t("noProductsHint")}</p>
        <button
          onClick={onClearFilters}
          className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#0D4D4D] px-4 py-2 text-xs font-medium text-white hover:bg-[#0a3d3d] transition-colors"
        >
          {t("clearFilters")}
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} categoryTree={categoryTree} />
      ))}
    </div>
  );
}
