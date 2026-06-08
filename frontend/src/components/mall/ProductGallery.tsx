"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import type { ProductImage } from "@/lib/api/products";

interface ProductGalleryProps {
  /** SPU 级图片(所有图片) */
  images: ProductImage[];
  /** 选中 SKU 的专属图片,有值时替换主图区 */
  skuImages?: ProductImage[];
  /** 是否精选商品 */
  isFeatured?: boolean;
}

export function ProductGallery({ images, skuImages, isFeatured }: ProductGalleryProps) {
  const t = useTranslations("mall");

  // SKU 有专属图时用 SKU 图,否则用 SPU 全部图
  const displayImages = useMemo(() => {
    const list = skuImages && skuImages.length > 0 ? skuImages : images;
    return [...list].sort((a, b) => a.sort_order - b.sort_order);
  }, [images, skuImages]);

  const [activeIndex, setActiveIndex] = useState(0);

  // 切换图片源时重置到第一张
  useEffect(() => {
    setActiveIndex(0);
  }, [displayImages]);

  const activeImage = displayImages[activeIndex] ?? null;

  return (
    <div className="shrink-0">
      {/* 主图 */}
      <div className="relative w-[320px] h-[260px] rounded-lg border border-gray-200 bg-gray-50 overflow-hidden">
        {activeImage ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={activeImage.full_url}
            alt=""
            className="h-full w-full object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-6xl text-gray-300">
            📷
          </div>
        )}
        {isFeatured && (
          <span className="absolute left-2 top-2 rounded bg-[#FF6B35] px-2 py-0.5 text-[10px] font-semibold text-white">
            {t("featured")}
          </span>
        )}
      </div>

      {/* 缩略图 */}
      {displayImages.length > 1 && (
        <div className="mt-2 flex gap-1.5 overflow-x-auto">
          {displayImages.map((img, idx) => (
            <button
              key={img.id}
              type="button"
              onClick={() => setActiveIndex(idx)}
              className={`relative h-14 w-14 shrink-0 rounded-md border-2 overflow-hidden transition-colors ${
                idx === activeIndex
                  ? "border-[#0D4D4D]"
                  : "border-gray-200 hover:border-gray-400"
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.full_url}
                alt=""
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
