"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

const AUTOPLAY_INTERVAL = 2000;

/** 主图固定（有按钮热区），不走动态加载 */
const HERO_SLIDE = {
  src: "/banners/hero-main.jpg",
  alt: "BuildReach - Source China Building Materials for East Africa",
  link: "/mall",
};

/** 文件名 → alt 文本：去掉扩展名，连字符转空格，首字母大写 */
function fileToAlt(name: string): string {
  return name
    .replace(/\.[^.]+$/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function HeroBannerCarousel() {
  const [slides, setSlides] = useState([HERO_SLIDE]);
  const [current, setCurrent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  // 从后端拉取 banner 文件列表
  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    fetch(`${apiBase}/api/v1/banners/slides`)
      .then((r) => r.json())
      .then((res) => {
        if (res.code === 0 && Array.isArray(res.data) && res.data.length > 0) {
          const dynamicSlides = res.data.map((name: string) => ({
            src: `/banners/${name}`,
            alt: fileToAlt(name),
            link: null,
          }));
          setSlides([HERO_SLIDE, ...dynamicSlides]);
        }
      })
      .catch(() => {
        // 接口不可用时保持 hero 单图
      });
  }, []);

  const count = slides.length;

  const goTo = useCallback(
    (idx: number) => setCurrent(((idx % count) + count) % count),
    [count],
  );
  const next = useCallback(() => goTo(current + 1), [current, goTo]);
  const prev = useCallback(() => goTo(current - 1), [current, goTo]);

  useEffect(() => {
    if (count <= 1 || isPaused) return;
    timerRef.current = setInterval(next, AUTOPLAY_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [count, isPaused, next]);

  return (
    <div
      className="relative w-full h-full rounded-xl overflow-hidden group"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {slides.map((slide, i) => {
        const img = (
          <img
            src={slide.src}
            alt={slide.alt}
            className="absolute inset-0 w-full h-full object-cover"
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
              <Link href={slide.link} className="block w-full h-full">{img}</Link>
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
