"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { bannersApi } from "@/lib/api/banners";
import { imageUrl } from "@/lib/env";

const AUTOPLAY_INTERVAL = Number(process.env.NEXT_PUBLIC_BANNER_INTERVAL_MS) || 5000;

/**
 * 首页轮播 — 动态从后端读取(GET /api/v1/banners，position="home_carousel")。
 * 播放顺序 = 后端按 sort_order 排序;运营在后台增删改 / 排序 / 上下架。
 * 存量图由 backend/scripts/seed_banners.py 一次性 seed 进库。
 */
interface Slide {
  src: string;
  alt: string;
  link: string | null;
}

/** 判断 slide 是否在当前可见窗口内（当前 ± 1），用于按需挂载 DOM */
function isNearby(index: number, current: number, total: number): boolean {
  if (index === current) return true;
  const prev = (current - 1 + total) % total;
  const next = (current + 1) % total;
  return index === prev || index === next;
}

export function HeroBannerCarousel() {
  const [slides, setSlides] = useState<Slide[]>([]);
  const [current, setCurrent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const count = slides.length;

  useEffect(() => {
    let alive = true;
    bannersApi
      .list("home_carousel")
      .then((rows) => {
        if (!alive) return;
        setSlides(
          rows.map((r) => ({
            src: imageUrl(r.image_url),
            alt: r.title || "",
            link: r.link_url,
          })),
        );
      })
      .catch(() => {
        /* 静默失败:轮播不显示,不阻塞首页 */
      });
    return () => {
      alive = false;
    };
  }, []);

  const goTo = useCallback(
    (idx: number) => setCurrent(count ? ((idx % count) + count) % count : 0),
    [count],
  );
  const next = useCallback(() => setCurrent((c) => (count ? (c + 1) % count : 0)), [count]);
  const prev = useCallback(() => setCurrent((c) => (count ? (c - 1 + count) % count : 0)), [count]);

  useEffect(() => {
    if (count <= 1 || isPaused) return;
    timerRef.current = setInterval(next, AUTOPLAY_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [count, isPaused, next]);

  // 加载中 / 无数据:保留占位背景,不塌陷布局
  if (count === 0) {
    return <div className="w-full h-full rounded-xl bg-gray-100" />;
  }

  return (
    <div
      className="relative w-full h-full rounded-xl overflow-hidden group"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {slides.map((slide, i) => {
        // 只渲染当前 ± 1 张，其余不挂载 DOM
        if (!isNearby(i, current, count)) return null;

        const img = (
          <img
            src={slide.src}
            alt={slide.alt}
            className="absolute inset-0 w-full h-full object-cover"
            loading={i === 0 ? "eager" : "lazy"}
            draggable={false}
          />
        );
        return (
          <div
            key={slide.src}
            className={`absolute inset-0 transition-opacity duration-700 ${
              i === current ? "opacity-100 z-[1]" : "opacity-0 z-0"
            }`}
          >
            {slide.link ? (
              <Link href={slide.link} className="block w-full h-full">
                {img}
              </Link>
            ) : (
              img
            )}
          </div>
        );
      })}

      {/* 左右箭头 */}
      {count > 1 && (
        <>
          <button
            onClick={prev}
            className="absolute left-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-black/30 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/50"
            aria-label="Previous"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={next}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-black/30 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/50"
            aria-label="Next"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </>
      )}

      {/* 圆点指示器 */}
      {count > 1 && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex gap-2">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i)}
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                i === current ? "bg-white" : "bg-white/40 hover:bg-white/70"
              }`}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
