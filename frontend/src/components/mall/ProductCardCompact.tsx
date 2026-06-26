"use client";

import { Link } from "@/i18n/navigation";
import { Package } from "lucide-react";

import type { ProductPublic } from "@/lib/api/products";

/**
 * 精简商品卡 — 品类楼层专用。
 * 相比列表页 ProductCard，去掉描述/徽章/供应模式/购物车按钮，更紧凑。
 */
export function ProductCardCompact({ product }: { product: ProductPublic }) {

  return (
    <Link
      href={`/mall/products/${product.id}`}
      className="group block rounded-lg border border-line bg-white overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-teal-700 hover:shadow-mall-md shadow-mall-sm"
    >
      {/* 图片区 */}
      <div
        className="relative aspect-square flex items-center justify-center overflow-hidden border-b border-[#edf2f5] p-1"
        style={{ background: "linear-gradient(135deg, #f0faf9, #fff)" }}
      >
        {product.main_image ? (
          <img
            src={product.main_image}
            alt={product.name}
            className="h-full w-full object-contain"
            loading="lazy"
          />
        ) : (
          <Package className="h-10 w-10 text-gray-300" />
        )}
      </div>

      {/* 信息区 */}
      <div className="p-2 space-y-1">
        <h3 className="text-[13px] font-bold leading-tight text-navy line-clamp-1 group-hover:text-teal-900">
          {product.name}
        </h3>

        {product.moq != null && (
          <p className="text-[11px] text-muted">
            <span className="font-bold text-navy">MOQ:</span>{" "}
            {product.moq.toLocaleString()} {product.moq_unit || product.unit || ""}
          </p>
        )}
      </div>
    </Link>
  );
}
