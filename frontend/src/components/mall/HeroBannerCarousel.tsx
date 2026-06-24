"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLocale } from "next-intl";
import Link from "next/link";
import useSWR from "swr";

import { bannersApi, type BannerSlide } from "@/lib/api/banners";

const AUTOPLAY_INTERVAL = 1500;

/**
 * 第一帧：设计图背景 + 透明热区可点击
 */
function HeroSlide({ active }: { active: boolean }) {
  return (
    <div
      className={`absolute inset-0 transition-opacity duration-700 ${
        active ? "opacity-100 z-[1]" : "opacity-0 z-0"
      }`}
    >
      <img
        src="/banners/hero-main.jpg"
        alt="BuildReach - Source China Building Materials for East Africa"
        className="absolute inset-0 w-full h-full object-cover object-center"
        draggable={false}
      />

      {/* Browse Products 热区 */}
      <Link
        href="/mall"
        className="absolute z-[2] rounded-md hover:bg-white/10 transition-colors"
        style={{ left: "5%", bottom: "40%", width: "15%", height: "8%" }}
        aria-label="Browse Products"
      />

      {/* WhatsApp Service 热区 */}
      <a
        href="https://wa.me/255697000000"
        target="_blank"
        rel="noopener noreferrer"
        className="absolute z-[2] rounded-md hover:bg-white/10 transition-colors"
        style={{ left: "22%", bottom: "40%", width: "15%", height: "8%" }}
        aria-label="WhatsApp Service"
      />
    </div>
  );
}

/**
 * 图片帧
 */
function ImageSlide({ slide, active }: { slide: BannerSlide; active: boolean }) {
  const inner = (
    <img
      src={slide.image_url}
      alt={slide.title || ""}
      className="absolute inset-0 w-full h-full object-cover"
      draggable={false}
    />
  );

  return (
    <div
      className={`absolute inset-0 transition-opacity duration-700 ${
        active ? "opacity-100 z-[1]" : "opacity-0 z-0"
      }`}
    >
      {slide.link_url ? (
        <Link href={slide.link_url} className="block w-full h-full">
          {inner}
        </Link>
      ) : (
        inner
      )}
    </div>
  );
}

export function HeroBannerCarousel() {
  const locale = useLocale();
  const { data: slides = [] } = useSWR(
    `/api/v1/banners?locale=${locale}`,
    () => bannersApi.list("home_carousel"),
    { revalidateOnFocus: false },
  );

  // 总帧数 = 1(Hero) + N(图片)
  const totalCount = 1 + slides.length;

  const [current, setCurrent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  const goTo = useCallback(
    (idx: number) => {
      setCurrent(((idx % totalCount) + totalCount) % totalCount);
    },
    [totalCount],
  );

  const next = useCallback(() => goTo(current + 1), [current, goTo]);
  const prev = useCallback(() => goTo(current - 1), [current, goTo]);

  // 自动轮播（有图片帧时才轮播）
  useEffect(() => {
    if (totalCount <= 1 || isPaused) return;
    timerRef.current = setInterval(next, AUTOPLAY_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [totalCount, isPaused, next]);

  return (
    <div
      className="relative w-full h-full rounded-xl overflow-hidden group"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {/* 第一帧：代码渲染的 Hero（支持 i18n） */}
      <HeroSlide active={current === 0} />

      {/* 后续帧：图片轮播 */}
      {slides.map((slide, i) => (
        <ImageSlide key={slide.id} slide={slide} active={current === i + 1} />
      ))}

      {/* 左右箭头(hover 显示) */}
      {totalCount > 1 && (
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
      {totalCount > 1 && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex gap-2">
          {Array.from({ length: totalCount }).map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i)}
              className={`w-2.5 h-2.5 rounded-full transition-all ${
                i === current
                  ? "bg-white scale-110"
                  : "bg-white/50 hover:bg-white/70"
              }`}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
