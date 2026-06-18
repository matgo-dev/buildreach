"use client";
import Link from "next/link";
import {
  ShoppingBag, Globe, Shield, ArrowRight,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { BRAND } from "@/config/brand";
import { MallButton } from "@/components/mall/MallButton";
import { LetterIcon } from "@/components/mall/LetterIcon";
import { SectionTitle } from "@/components/mall/SectionTitle";
import { MallCard } from "@/components/mall/MallCard";
import { CategorySidebar } from "@/components/mall/CategorySidebar";
import { RightSidebar } from "@/components/mall/RightSidebar";

// ─── 能力卡片 ───
const CAPABILITIES: { icon: LucideIcon; titleKey: string; descKey: string; color: string }[] = [
  { icon: ShoppingBag, titleKey: "capItem1Title", descKey: "capItem1Desc", color: "bg-teal-800" },
  { icon: Shield,      titleKey: "capItem2Title", descKey: "capItem2Desc", color: "bg-gold" },
  { icon: Globe,       titleKey: "capItem3Title", descKey: "capItem3Desc", color: "bg-emerald-600" },
  { icon: Truck,       titleKey: "capItem4Title", descKey: "capItem4Desc", color: "bg-teal-900" },
];

// ─── 服务承诺快捷卡片 ───
const SERVICE_CARDS: { letter: string; titleKey: string; sub: string }[] = [
  { letter: "SKU", titleKey: "svcCatalog",   sub: "Building Materials" },
  { letter: "CS",  titleKey: "svcQuote",     sub: "Quote Sheet / PI" },
  { letter: "C",   titleKey: "svcCompliance", sub: "PVoC / CoC / BL" },
  { letter: "20",  titleKey: "svcContainer", sub: "Shared Container" },
  { letter: "PI",  titleKey: "svcPayment",   sub: "Company Account" },
  { letter: "BOM", titleKey: "svcBom",       sub: "Photo / BOM RFQ" },
];

// ─── Hero 右侧亮点 ───
const HERO_STATS = [
  { icon: "📦", valueKey: "heroStat1Value", labelKey: "heroStat1Label" },
  { icon: "🏭", valueKey: "heroStat2Value", labelKey: "heroStat2Label" },
  { icon: "🚢", valueKey: "heroStat3Value", labelKey: "heroStat3Label" },
  { icon: "✅", valueKey: "heroStat4Value", labelKey: "heroStat4Label" },
];

// ─── Hero 徽章 ───
const BADGE_KEYS = [
  "heroBadge1", "heroBadge2", "heroBadge3",
  "heroBadge4", "heroBadge5", "heroBadge6",
];

// 置灰按钮
function DisabledCta({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`cursor-not-allowed select-none opacity-50 ${className}`}>
      {children}
    </span>
  );
}

export default function HomePage() {
  const t = useTranslations("mall");

  return (
    <PublicLayout>
      {/* 三栏布局:与商城页共用结构 */}
      <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_300px] gap-5 items-start">
        {/* ===== 左侧品类导航 ===== */}
        <CategorySidebar />

        {/* ===== 中间主内容 ===== */}
        <div className="min-w-0 space-y-5">
          {/* ── Hero Banner ── */}
          <section
            className="relative rounded-2xl overflow-hidden min-h-[340px] p-10 lg:p-12 grid lg:grid-cols-[1.3fr_1fr] gap-9 items-center"
            style={{
              background: "linear-gradient(120deg, #003f46 0%, #00505a 40%, #006773 70%, #07808b 100%)",
              boxShadow: "0 24px 60px rgba(0,55,62,.32)",
            }}
          >
            {/* 装饰光晕 */}
            <div className="absolute inset-0 pointer-events-none" style={{
              background: "radial-gradient(420px 320px at 86% 14%, rgba(227,166,21,.22), transparent 60%), radial-gradient(560px 420px at 12% 92%, rgba(7,128,139,.5), transparent 62%)",
            }} />

            <div className="relative z-10">
              <span
                className="inline-flex items-center gap-2 min-h-[30px] px-3.5 rounded-full text-[12.5px] font-extrabold text-[#d6fffb] uppercase tracking-wider mb-4"
                style={{ background: "rgba(255,255,255,0.14)", border: "1px solid rgba(255,255,255,0.22)", backdropFilter: "blur(6px)" }}
              >
                <span className="w-[7px] h-[7px] rounded-full bg-gold" style={{ boxShadow: "0 0 10px #e3a615" }} />
                {t("heroEyebrow")}
              </span>

              <h1 className="text-white font-black leading-[1.08] mb-2" style={{ fontSize: "clamp(30px, 3vw, 44px)", textShadow: "0 2px 20px rgba(0,30,34,.3)" }}>
                {t("heroHeadline")}
                <span className="block mt-2 text-gold font-extrabold" style={{ fontSize: "clamp(20px, 2vw, 28px)" }}>
                  {BRAND.tagline}
                </span>
              </h1>

              <p className="text-[#dff1f0] text-[15px] leading-relaxed max-w-[620px] mb-5">
                {t("heroDesc")}
              </p>

              <div className="flex flex-wrap gap-2.5 mb-5">
                <MallButton variant="gold" href="/mall">{t("heroCtaStart")}</MallButton>
                <MallButton variant="outline" href="/buyer/cart">
                  {t("heroCtaQuote")}
                </MallButton>
                <DisabledCta>
                  <span className="h-10 px-4 inline-flex items-center rounded-[10px] text-sm font-extrabold text-white" style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.24)" }}>
                    {t("heroCtaContainer")}
                  </span>
                </DisabledCta>
              </div>

              {/* 徽章行 */}
              <div className="flex flex-wrap gap-2.5">
                {BADGE_KEYS.map((key) => (
                  <span key={key} className="min-h-[42px] inline-flex items-center gap-2 px-3 py-2 rounded-lg text-white text-xs font-extrabold"
                    style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.22)", backdropFilter: "blur(6px)" }}>
                    {t(key)}
                  </span>
                ))}
              </div>
            </div>

            {/* 右侧：平台亮点数据 — 撑满左侧高度 */}
            <div className="hidden lg:flex flex-col justify-between gap-2 relative z-10 w-full max-w-[320px] self-stretch">
              {HERO_STATS.map((stat, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg px-5 py-4 flex-1"
                  style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)" }}>
                  <span className="text-3xl">{stat.icon}</span>
                  <div>
                    <div className="text-[20px] font-bold text-[#e3a615] leading-none">{t(stat.valueKey)}</div>
                    <div className="text-[12px] text-white/60 mt-1">{t(stat.labelKey)}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── 服务承诺快捷行 ── */}
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-3">
            {SERVICE_CARDS.map((svc) => (
              <MallCard key={svc.letter} padding="p-3" className="flex items-center gap-2.5 min-h-[72px]">
                <LetterIcon letter={svc.letter} size={26} />
                <span>
                  <strong className="block text-[13px] text-navy leading-tight">{t(svc.titleKey)}</strong>
                  <small className="text-muted text-[11px]">{svc.sub}</small>
                </span>
              </MallCard>
            ))}
          </div>

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
              <DisabledCta>
                <span className="h-10 px-6 inline-flex items-center rounded-[10px] text-sm font-extrabold text-white" style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.24)" }}>
                  {t("ctaLearnMore")}
                </span>
              </DisabledCta>
            </div>
          </div>
        </div>

        {/* ===== 右侧栏 ===== */}
        <RightSidebar />
      </div>
    </PublicLayout>
  );
}
