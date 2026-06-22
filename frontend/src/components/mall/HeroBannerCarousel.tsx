"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Package, Factory, Ship, CheckCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import useSWR from "swr";

import { bannersApi, type BannerSlide } from "@/lib/api/banners";
import { MallButton } from "./MallButton";
import { BRAND } from "@/config/brand";

const AUTOPLAY_INTERVAL = 1500;

// ─── Hero 右侧亮点数据 ───
const HERO_STATS = [
  { icon: Package, valueKey: "heroStat1Value", labelKey: "heroStat1Label" },
  { icon: Factory, valueKey: "heroStat2Value", labelKey: "heroStat2Label" },
  { icon: Ship, valueKey: "heroStat3Value", labelKey: "heroStat3Label" },
  { icon: CheckCircle, valueKey: "heroStat4Value", labelKey: "heroStat4Label" },
];

// ─── Hero 徽章 ───
const BADGE_KEYS = [
  "heroBadge1", "heroBadge2", "heroBadge3",
  "heroBadge4", "heroBadge5", "heroBadge6",
];

/**
 * 第一帧：代码渲染的品牌 Hero（支持 i18n）
 */
function HeroSlide({ active }: { active: boolean }) {
  const t = useTranslations("mall");

  return (
    <div
      className={`absolute inset-0 transition-opacity duration-700 ${
        active ? "opacity-100 z-[1]" : "opacity-0 z-0"
      }`}
    >
      <div
        className="w-full h-full p-8 lg:p-10 flex items-center justify-center"
        style={{
          background: "linear-gradient(120deg, #003f46 0%, #00505a 40%, #006773 70%, #07808b 100%)",
        }}
      >
        {/* 装饰光晕 */}
        <div className="absolute inset-0 pointer-events-none" style={{
          background: "radial-gradient(420px 320px at 86% 14%, rgba(227,166,21,.18), transparent 60%), radial-gradient(560px 420px at 12% 92%, rgba(7,128,139,.4), transparent 62%)",
        }} />

        <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6 items-center w-full max-w-[900px]">
          <div className="relative z-10">
            <h1 className="text-white font-black leading-[1.1] mb-2" style={{ fontSize: "clamp(20px, 2.2vw, 32px)", textShadow: "0 2px 16px rgba(0,30,34,.3)" }}>
              {t("heroHeadline")}
              <span className="block mt-1.5 text-gold font-extrabold" style={{ fontSize: "clamp(14px, 1.4vw, 20px)" }}>
                {BRAND.tagline}
              </span>
            </h1>

            <p className="text-[#dff1f0] text-[13px] leading-relaxed max-w-[520px] mb-4">
              {t("heroDesc")}
            </p>

            <div className="flex flex-wrap gap-2 mb-4">
              <MallButton variant="gold" href="/mall">{t("heroCtaStart")}</MallButton>
              <MallButton variant="outline" href="/buyer/cart">{t("heroCtaQuote")}</MallButton>
            </div>

            {/* 徽章行 */}
            <div className="flex flex-wrap gap-1.5">
              {BADGE_KEYS.map((key) => (
                <span key={key} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-white text-[11px] font-bold"
                  style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.18)" }}>
                  {t(key)}
                </span>
              ))}
            </div>
          </div>

          {/* 右侧亮点数据 */}
          <div className="hidden lg:flex flex-col justify-center gap-2 relative z-10">
            {HERO_STATS.map((stat, i) => {
              const Icon = stat.icon;
              return (
                <div key={i} className="flex items-center gap-3 rounded-lg px-4 py-3"
                  style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.12)" }}>
                  <Icon className="w-6 h-6 text-gold shrink-0" />
                  <div>
                    <div className="text-lg font-bold text-gold leading-none">{t(stat.valueKey)}</div>
                    <div className="text-[11px] text-white/60 mt-0.5">{t(stat.labelKey)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
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
      className="relative w-full h-full min-h-[320px] rounded-xl overflow-hidden group"
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
