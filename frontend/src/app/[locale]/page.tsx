"use client";
import {
  ShoppingBag, Globe, Shield,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { MallButton } from "@/components/mall/MallButton";
import { SectionTitle } from "@/components/mall/SectionTitle";
import { MallCard } from "@/components/mall/MallCard";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { RightSidebar } from "@/components/mall/RightSidebar";
import { HeroBannerCarousel } from "@/components/mall/HeroBannerCarousel";
import { CategoryFloors } from "@/components/mall/CategoryFloors";

// ─── 能力卡片 ───
const CAPABILITIES: { icon: LucideIcon; titleKey: string; descKey: string; color: string }[] = [
  { icon: ShoppingBag, titleKey: "capItem1Title", descKey: "capItem1Desc", color: "bg-teal-800" },
  { icon: Shield,      titleKey: "capItem2Title", descKey: "capItem2Desc", color: "bg-gold" },
  { icon: Globe,       titleKey: "capItem3Title", descKey: "capItem3Desc", color: "bg-emerald-600" },
  { icon: Truck,       titleKey: "capItem4Title", descKey: "capItem4Desc", color: "bg-teal-900" },
];

export default function HomePage() {
  const t = useTranslations("mall");

  return (
    <PublicLayout>
      {/* ===== 顶部三栏等高区域(品类 + 轮播 + 信息栏) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)_220px] gap-4 items-stretch mb-5 lg:h-[420px] xl:h-[460px]">
        {/* 左侧品类导航 — home 模式不 sticky */}
        <CategorySidebar variant="home" />

        {/* 中间轮播 Banner */}
        <HeroBannerCarousel />

        {/* 右侧信息栏 — home 模式不 sticky */}
        <RightSidebar variant="home" />
      </div>

      {/* ===== 品类楼层区 ===== */}
      <div className="mb-5">
        <CategoryFloors />
      </div>

      {/* ===== 下方内容区 ===== */}
      <div className="space-y-5">
        {/* ── 平台核心能力 ── */}
        <MallCard padding="p-6">
          <SectionTitle sub="Platform Capabilities" className="mb-4">{t("capTitle")}</SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {CAPABILITIES.map(({ icon: Icon, titleKey, descKey, color }) => (
              <div key={titleKey} className="p-4 rounded-lg border border-line hover:shadow-mall-md hover:-translate-y-0.5 transition-all">
                <div className={`w-[38px] h-[38px] rounded-lg ${color} grid place-items-center mb-3`}
                  style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,.18), 0 4px 10px rgba(0,63,70,.18)" }}>
                  <Icon className="w-4 h-4 text-white" />
                </div>
                <h3 className="text-sm font-black text-navy mb-1">{t(titleKey)}</h3>
                <p className="text-xs text-muted leading-relaxed">{t(descKey)}</p>
              </div>
            ))}
          </div>
        </MallCard>

        {/* ── 底部 CTA ── */}
        <div className="rounded-xl p-10 text-center text-white" style={{
          background: "linear-gradient(120deg, #003f46, #00505a 60%, #006773)",
        }}>
          <h2 className="text-xl font-black mb-2">{t("ctaTitle")}</h2>
          <p className="text-white/50 text-sm mb-5">{t("ctaDesc")}</p>
          <div className="flex justify-center gap-3">
            <MallButton variant="gold" href="/register">{t("ctaRegister")}</MallButton>
            <MallButton variant="outline" href="/how-to-buy">{t("ctaLearnMore")}</MallButton>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}
