"use client";

import { useTranslations } from "next-intl";
import { Search, AlertCircle, RefreshCw } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { ProductCard } from "./ProductCard";
import { MallButton } from "./MallButton";

interface Props {
  products: ProductPublic[];
  categoryTree: CategoryTreeNode[];
  isLoading: boolean;
  error: Error | undefined;
  onRetry: () => void;
  onClearFilters: () => void;
}

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-line bg-white overflow-hidden shadow-mall-sm">
      <div className="min-h-[152px] bg-teal-50" />
      <div className="p-3.5 space-y-2">
        <div className="h-4 w-full rounded bg-gray-100" />
        <div className="h-3 w-24 rounded bg-gray-100" />
        <div className="h-3 w-16 rounded bg-gray-100" />
        <div className="h-10 w-full rounded-[10px] bg-gray-100" />
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

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
        {Array.from({ length: 10 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-line bg-white py-20 text-center shadow-mall-sm">
        <AlertCircle className="mx-auto mb-3 h-10 w-10 text-red-300" />
        <p className="text-sm font-extrabold text-navy">{t("loadError")}</p>
        <MallButton variant="teal" size="sm" onClick={onRetry} className="mt-3">
          <RefreshCw className="h-3.5 w-3.5" />
          {t("retry")}
        </MallButton>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="rounded-xl border border-line bg-white py-20 text-center shadow-mall-sm">
        <Search className="mx-auto mb-3 h-10 w-10 text-gray-300" />
        <p className="text-sm font-extrabold text-navy">{t("noProducts")}</p>
        <p className="mt-1 text-xs text-muted">{t("noProductsHint")}</p>
        <MallButton variant="teal" size="sm" onClick={onClearFilters} className="mt-3">
          {t("clearFilters")}
        </MallButton>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} categoryTree={categoryTree} />
      ))}
    </div>
  );
}
