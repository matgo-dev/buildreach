"use client";
import { MessageCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { MallButton, MALL_BTN_ON_DARK } from "@/components/mall/MallButton";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { RightSidebar } from "@/components/mall/RightSidebar";
import { HeroBannerCarousel } from "@/components/mall/HeroBannerCarousel";
import { MobileCategoryGrid } from "@/components/mall/MobileCategoryGrid";
import { CategoryFloors } from "@/components/mall/CategoryFloors";
import { useAuthStore } from "@/stores/authStore";
import { ContactPopover } from "@/components/mall/ContactPopover";

export default function HomePage() {
  const t = useTranslations("mall");

  return (
    <PublicLayout>
      {/* ===== 顶部三栏等高区域(品类 + 轮播 + 信息栏) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)_220px] gap-4 items-stretch mb-5 h-[200px] sm:h-[260px] lg:h-[420px] xl:h-[460px]">
        {/* 左侧品类导航 — home 模式不 sticky */}
        <CategorySidebar variant="home" />

        {/* 中间轮播 Banner */}
        <HeroBannerCarousel />

        {/* 右侧信息栏 — home 模式不 sticky */}
        <RightSidebar variant="home" />
      </div>

      {/* ===== 移动端品类入口(仅 <lg 显示) ===== */}
      <MobileCategoryGrid />

      {/* ===== 品类楼层区 ===== */}
      <div className="mb-5">
        <CategoryFloors />
      </div>

      {/* ===== 下方内容区 ===== */}
      <div className="space-y-5">
        {/* ── 底部 CTA ── */}
        <BottomCta />
      </div>
    </PublicLayout>
  );
}

/** 底部 CTA — 未登录：注册引导 / 已登录：采购动作 + WhatsApp */
function BottomCta() {
  const t = useTranslations("mall");
  const user = useAuthStore((s) => s.user);

  return (
    <div className="rounded-xl border-t-[3px] border-t-lime bg-gradient-to-br from-teal-800 to-teal-950 p-10 text-center text-white">
      {user ? (
        <>
          <h2 className="text-xl font-black mb-2">{t("ctaLoggedInTitle")}</h2>
          <p className="text-white/70 text-sm mb-5">{t("ctaLoggedInDesc")}</p>
          <div className="flex justify-center gap-3 flex-wrap">
            <MallButton variant="lime" href="/mall">{t("ctaBrowseMall")}</MallButton>
            <MallButton href="/order-tracking" variant="onDark">{t("ctaTrackOrder")}</MallButton>
            <ContactPopover>
              <button className={`inline-flex items-center gap-1.5 rounded-lg px-6 py-2.5 text-sm font-bold transition-colors ${MALL_BTN_ON_DARK}`}>
                <MessageCircle className="h-4 w-4" />
                {t("ctaContactUs")}
              </button>
            </ContactPopover>
          </div>
        </>
      ) : (
        <>
          <h2 className="text-xl font-black mb-2">{t("ctaTitle")}</h2>
          <p className="text-white/70 text-sm mb-5">{t("ctaDesc")}</p>
          <div className="flex justify-center gap-3">
            <MallButton variant="lime" href="/register">{t("ctaRegister")}</MallButton>
            <MallButton href="/how-to-buy" variant="onDark">{t("ctaLearnMore")}</MallButton>
          </div>
        </>
      )}
    </div>
  );
}
