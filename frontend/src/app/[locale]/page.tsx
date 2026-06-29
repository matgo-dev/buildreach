"use client";
import { MessageCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { MallButton } from "@/components/mall/MallButton";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { RightSidebar } from "@/components/mall/RightSidebar";
import { HeroBannerCarousel } from "@/components/mall/HeroBannerCarousel";
import { MobileCategoryGrid } from "@/components/mall/MobileCategoryGrid";
import { CategoryFloors } from "@/components/mall/CategoryFloors";
import { useAuthStore } from "@/stores/authStore";
import { useWhatsApp } from "@/hooks/useWhatsApp";

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
  const wa = useWhatsApp();

  return (
    <div className="rounded-xl p-10 text-center text-white" style={{
      background: "linear-gradient(120deg, #003f46, #00505a 60%, #006773)",
    }}>
      {user ? (
        <>
          <h2 className="text-xl font-black mb-2">{t("ctaLoggedInTitle")}</h2>
          <p className="text-white/50 text-sm mb-5">{t("ctaLoggedInDesc")}</p>
          <div className="flex justify-center gap-3 flex-wrap">
            <MallButton variant="gold" href="/mall">{t("ctaBrowseMall")}</MallButton>
            <MallButton variant="outline" href="/order-tracking">{t("ctaTrackOrder")}</MallButton>
            {wa.link && (
              <a
                href={wa.buildLink() ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full bg-[#25D366] px-6 py-2.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-[#1fb855]"
              >
                <MessageCircle className="h-4 w-4" />
                {t("ctaWhatsApp")}
              </a>
            )}
          </div>
        </>
      ) : (
        <>
          <h2 className="text-xl font-black mb-2">{t("ctaTitle")}</h2>
          <p className="text-white/50 text-sm mb-5">{t("ctaDesc")}</p>
          <div className="flex justify-center gap-3">
            <MallButton variant="gold" href="/register">{t("ctaRegister")}</MallButton>
            <MallButton variant="outline" href="/how-to-buy">{t("ctaLearnMore")}</MallButton>
          </div>
        </>
      )}
    </div>
  );
}
