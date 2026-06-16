"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
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

  // SKU 有专属图时：SKU 图排前 + SPU 图排后（去重），保证缩略图不丢
  const displayImages = useMemo(() => {
    if (skuImages && skuImages.length > 0) {
      const skuSorted = [...skuImages].sort((a, b) => a.sort_order - b.sort_order);
      const skuIds = new Set(skuSorted.map((img) => img.id));
      const spuRest = images
        .filter((img) => !skuIds.has(img.id))
        .sort((a, b) => a.sort_order - b.sort_order);
      return [...skuSorted, ...spuRest];
    }
    return [...images].sort((a, b) => a.sort_order - b.sort_order);
  }, [images, skuImages]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  // 切换图片源时重置到第一张
  useEffect(() => {
    setActiveIndex(0);
  }, [displayImages]);

  const activeImage = displayImages[activeIndex] ?? null;

  // 悬浮放大：鼠标在主图上移动时原地显示放大局部
  const [zooming, setZooming] = useState(false);
  const [zoomPos, setZoomPos] = useState({ x: 0, y: 0 }); // 0~1 比例
  const mainRef = useRef<HTMLDivElement>(null);
  const ZOOM_SCALE = 2.5;

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    setZoomPos({ x, y });
  }, []);

  const openLightbox = useCallback(() => {
    if (activeImage) setLightboxOpen(true);
  }, [activeImage]);

  const goPrev = useCallback(() => {
    setActiveIndex((i) => (i > 0 ? i - 1 : displayImages.length - 1));
  }, [displayImages.length]);

  const goNext = useCallback(() => {
    setActiveIndex((i) => (i < displayImages.length - 1 ? i + 1 : 0));
  }, [displayImages.length]);

  // 键盘导航
  useEffect(() => {
    if (!lightboxOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxOpen, goPrev, goNext]);

  return (
    <div className="shrink-0">
      {/* 主图 — 悬浮原地放大 */}
      <div
        ref={mainRef}
        className="relative w-[400px] h-[360px] rounded-lg border border-gray-200 bg-gray-50 overflow-hidden cursor-crosshair"
        onClick={openLightbox}
        onMouseEnter={() => setZooming(true)}
        onMouseLeave={() => setZooming(false)}
        onMouseMove={handleMouseMove}
      >
        {activeImage ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={activeImage.full_url}
              alt=""
              className={`h-full w-full object-contain transition-opacity duration-150 ${zooming ? "opacity-0" : "opacity-100"}`}
            />
            {/* 放大层：用 background-image 实现局部放大 */}
            {zooming && (
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `url(${activeImage.full_url})`,
                  backgroundSize: `${ZOOM_SCALE * 100}%`,
                  backgroundPosition: `${zoomPos.x * 100}% ${zoomPos.y * 100}%`,
                  backgroundRepeat: "no-repeat",
                }}
              />
            )}
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-6xl text-gray-300">
            📷
          </div>
        )}
        {isFeatured && (
          <span className="absolute left-2 top-2 rounded bg-[#15935f] px-2 py-0.5 text-[10px] font-semibold text-white">
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
              onMouseEnter={() => setActiveIndex(idx)}
              className={`relative h-14 w-14 shrink-0 rounded-md border-2 overflow-hidden transition-colors ${
                idx === activeIndex
                  ? "border-[#00505a]"
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

      {/* Lightbox 全屏预览 */}
      {lightboxOpen && activeImage && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80"
          onClick={() => setLightboxOpen(false)}
        >
          {/* 关闭按钮 */}
          <button
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 transition-colors"
            onClick={() => setLightboxOpen(false)}
          >
            <X className="h-6 w-6" />
          </button>

          {/* 计数器 */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 text-sm text-white/70">
            {activeIndex + 1} / {displayImages.length}
          </div>

          {/* 上一张 */}
          {displayImages.length > 1 && (
            <button
              className="absolute left-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 transition-colors"
              onClick={(e) => { e.stopPropagation(); goPrev(); }}
            >
              <ChevronLeft className="h-8 w-8" />
            </button>
          )}

          {/* 大图 — 小图也撑到合理尺寸 */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={activeImage.full_url}
            alt=""
            className="max-h-[85vh] max-w-[90vw] min-h-[50vh] min-w-[40vw] object-contain"
            onClick={(e) => e.stopPropagation()}
          />

          {/* 下一张 */}
          {displayImages.length > 1 && (
            <button
              className="absolute right-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20 transition-colors"
              onClick={(e) => { e.stopPropagation(); goNext(); }}
            >
              <ChevronRight className="h-8 w-8" />
            </button>
          )}

          {/* 底部缩略图 */}
          {displayImages.length > 1 && (
            <div className="absolute bottom-6 flex gap-2 overflow-x-auto px-4">
              {displayImages.map((img, idx) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setActiveIndex(idx); }}
                  className={`h-12 w-12 shrink-0 rounded-md border-2 overflow-hidden transition-colors ${
                    idx === activeIndex ? "border-white" : "border-transparent opacity-50 hover:opacity-80"
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={img.full_url} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
