"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

const AUTOPLAY_INTERVAL = 2000;

/** MVP 固定 banner 列表 — 后续可改为后台管理 */
const SLIDES = [
  { src: "/banners/hero-main.jpg", alt: "BuildReach - Source China Building Materials for East Africa", link: "/mall" },
  { src: "/banners/factory-aerial-view.jpg", alt: "Factory Aerial View", link: null },
  { src: "/banners/factory-production-line.jpg", alt: "Production Line", link: null },
  { src: "/banners/factory-steel-products.jpg", alt: "Steel Products", link: null },
  { src: "/banners/factory-steel-coils.jpg", alt: "Steel Coils Workshop", link: null },
  { src: "/banners/factory-exterior.jpg", alt: "Factory Exterior", link: null },
  { src: "/banners/factory-industrial-furnace.jpg", alt: "Industrial Furnace", link: null },
  { src: "/banners/factory-palletizing-robot.jpg", alt: "Palletizing Robot", link: null },
  { src: "/banners/factory-packaging-robot.jpg", alt: "Packaging Robot", link: null },
  { src: "/banners/factory-coating-workshop.jpg", alt: "Coating Workshop", link: null },
  { src: "/banners/factory-mesh-rolls.jpg", alt: "Mesh Rolls Warehouse", link: null },
  { src: "/banners/factory-crate-packing.jpg", alt: "Crate Packing Warehouse", link: null },
  { src: "/banners/factory-decorative-panels.jpg", alt: "Decorative Panels Production", link: null },
];

export function HeroBannerCarousel() {
  const [current, setCurrent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const count = SLIDES.length;

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
      {SLIDES.map((slide, i) => {
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
          {SLIDES.map((_, i) => (
            <button
              key={i}
              onClick={() => goTo(i)}
              className={`w-2.5 h-2.5 rounded-full transition-all ${
                i === current ? "bg-white scale-110" : "bg-white/50 hover:bg-white/70"
              }`}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
