"use client";
import Link from "next/link";
import {
  ShoppingBag, Globe, Shield, Bot, ArrowRight, Building2,
  Truck, Zap, Package, Wrench,
  Flame, MoveUp, Columns3, Droplets, PaintBucket, Umbrella,
  type LucideIcon,
} from "lucide-react";

import { useTranslations } from "next-intl";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { BRAND } from "@/config/brand";
import { MallButton } from "@/components/mall/MallButton";
import { LetterIcon } from "@/components/mall/LetterIcon";
import { SectionTitle } from "@/components/mall/SectionTitle";
import { MallCard } from "@/components/mall/MallCard";

const CATEGORIES: { code: string; name: string; nameEn: string; icon: LucideIcon }[] = [
  { code: "LIGHTING",     name: "照明电气",  nameEn: "Lighting & Electrical", icon: Zap },
  { code: "SANITARY",     name: "卫浴五金",  nameEn: "Sanitary Ware",         icon: Droplets },
  { code: "PIPES",        name: "管材管件",  nameEn: "Pipes & Fittings",      icon: Wrench },
  { code: "TOOLS",        name: "工具五金",  nameEn: "Tools & Hardware",      icon: Wrench },
  { code: "BOARDS",       name: "板材吊顶",  nameEn: "Boards & Ceiling",      icon: Columns3 },
  { code: "SAFETY",       name: "劳保用品",  nameEn: "Safety Gear",           icon: Shield },
  { code: "PROFILES",     name: "型材门窗",  nameEn: "Profiles & Windows",    icon: Building2 },
  { code: "PAINTS",       name: "涂料化工",  nameEn: "Paints & Chemicals",    icon: PaintBucket },
  { code: "STRUCTURAL",   name: "结构建材",  nameEn: "Structural Materials",  icon: Package },
];

const FOUR_CAPABILITIES = [
  { icon: ShoppingBag, title: "建材采购商城",   titleEn: "Product Sourcing",     desc: "9 大品类、200+ 中国优质建材供应商，一站式选品询价", color: "bg-teal-800" },
  { icon: Shield,      title: "供应商信用体系", titleEn: "Supplier Verification", desc: "严格审核准入，T1/T2/T3 分级管理，确保供货质量",     color: "bg-gold" },
  { icon: Globe,       title: "进口合规支持",   titleEn: "Compliance Support",   desc: "PVoC/CoC/TBS 等东非进口认证文件全流程支持",         color: "bg-emerald-600" },
  { icon: Truck,       title: "拼柜集运追踪",   titleEn: "Container Tracking",   desc: "拼箱打包统一报关，12 节点全链路物流追踪",           color: "bg-teal-900" },
];

// 置灰按钮:用于跳转目标尚未实现的 CTA
function DisabledCta({ children, className = "", title = "功能开发中" }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      aria-disabled
      className={`cursor-not-allowed select-none opacity-50 ${className}`}
    >
      {children}
    </span>
  );
}

export default function HomePage() {
  const t = useTranslations("mall");
  return (
    <PublicLayout noContainer>
      {/* ===== HERO — 深青渐变 + 暖金点缀 ===== */}
      <section className="relative overflow-hidden" style={{
        minHeight: 420,
        background: "linear-gradient(120deg, #003f46 0%, #00505a 40%, #006773 70%, #07808b 100%)",
      }}>
        {/* 装饰光晕 */}
        <div className="absolute inset-0 pointer-events-none" style={{
          background: "radial-gradient(420px 320px at 86% 14%, rgba(227,166,21,.22), transparent 60%), radial-gradient(560px 420px at 12% 92%, rgba(7,128,139,.5), transparent 62%)",
        }} />
        <div className="absolute inset-0 pointer-events-none" style={{
          background: "radial-gradient(700px 240px at 50% -30%, rgba(255,255,255,.1), transparent 70%)",
        }} />

        <div className="relative mx-auto max-w-mall px-6 py-14 lg:py-20 z-10">
          <div className="grid lg:grid-cols-[1.3fr_1fr] gap-10 items-center">
            {/* 左侧:文案 */}
            <div>
              <div className="inline-flex items-center gap-2 min-h-[30px] px-3.5 rounded-full text-[12.5px] font-extrabold text-[#d6fffb] uppercase tracking-wider"
                style={{ background: "rgba(255,255,255,0.14)", border: "1px solid rgba(255,255,255,0.22)", backdropFilter: "blur(6px)" }}>
                <span className="w-[7px] h-[7px] rounded-full bg-gold" style={{ boxShadow: "0 0 10px #e3a615" }} />
                {t("heroEyebrow")}
              </div>

              <h1 className="mt-4 mb-3 text-white font-black leading-[1.15]" style={{ fontSize: "clamp(32px, 3.2vw, 48px)", textShadow: "0 2px 20px rgba(0,30,34,.3)" }}>
                {t("heroHeadline")}
                <span className="block mt-2 text-gold font-extrabold" style={{ fontSize: "clamp(20px, 2vw, 27px)" }}>
                  {BRAND.tagline}
                </span>
              </h1>

              <p className="text-[#e3f3f2] text-[15.5px] leading-relaxed max-w-[620px] mb-6">
                {t("heroDesc")}
              </p>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/mall"
                  className="h-10 px-5 inline-flex items-center justify-center rounded-[10px] text-sm font-extrabold text-white transition-all hover:-translate-y-0.5"
                  style={{
                    background: "linear-gradient(135deg, #f0b734, #e3a615, #c1850b)",
                    boxShadow: "0 10px 24px rgba(193,133,11,.4)",
                  }}
                >
                  {t("heroCtaStart")}
                </Link>
                <DisabledCta className="h-10 px-5 inline-flex items-center justify-center rounded-[10px] text-sm font-extrabold text-white" title="功能开发中">
                  <span style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.24)", borderRadius: 10, padding: "0 16px", height: 40, display: "inline-flex", alignItems: "center" }}>
                    {t("heroCtaQuote")}
                  </span>
                </DisabledCta>
                <DisabledCta className="h-10 px-5 inline-flex items-center justify-center rounded-[10px] text-sm font-extrabold text-white" title="功能开发中">
                  <span style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.24)", borderRadius: 10, padding: "0 16px", height: 40, display: "inline-flex", alignItems: "center" }}>
                    {t("heroCtaContainer")}
                  </span>
                </DisabledCta>
              </div>
            </div>

            {/* 右侧:产品展示台(占位) */}
            <div className="hidden lg:grid place-items-center">
              <div className="w-full max-w-[400px] min-h-[250px] grid grid-cols-3 gap-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-2xl flex items-center justify-center"
                    style={{
                      background: i === 0 ? "rgba(216,139,0,0.22)" : i === 3 ? "rgba(21,147,95,0.2)" : "rgba(255,255,255,0.1)",
                      border: `1px solid ${i === 0 ? "rgba(216,139,0,0.3)" : i === 3 ? "rgba(21,147,95,0.3)" : "rgba(255,255,255,0.16)"}`,
                      backdropFilter: "blur(6px)",
                      aspectRatio: "1 / 1.18",
                    }}
                  >
                    <Package className="h-8 w-8 text-white/40" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 品类快捷入口 ===== */}
      <section className="bg-bg">
        <div className="mx-auto max-w-mall px-6 py-8">
          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-3.5">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              const letter = cat.nameEn[0];
              return (
                <Link
                  key={cat.code}
                  href="/mall"
                  className="flex items-center gap-2.5 min-h-[76px] p-3 rounded-xl border border-line bg-white shadow-mall-sm hover:shadow-mall-md hover:-translate-y-0.5 transition-all group"
                >
                  <LetterIcon letter={letter} className="transition-all group-hover:scale-110" />
                  <span>
                    <strong className="block text-[13px] text-navy leading-tight">{cat.name}</strong>
                    <small className="text-muted text-[11px]">{cat.nameEn}</small>
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== 平台核心能力 ===== */}
      <section className="bg-white py-12">
        <div className="mx-auto max-w-mall px-6">
          <SectionTitle sub="Platform Capabilities">{t("capTitle")}</SectionTitle>
          <p className="text-muted text-xs mb-6">{t("capSubtitle")}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FOUR_CAPABILITIES.map((item) => {
              const Icon = item.icon;
              return (
                <MallCard
                  key={item.title}
                  padding="p-5"
                  hoverable
                >
                  <div className={`w-[38px] h-[38px] rounded-lg ${item.color} grid place-items-center mb-4`}
                    style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,.18), 0 4px 10px rgba(0,63,70,.18)" }}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-[15px] font-black text-navy mb-1">{item.title}</h3>
                  <p className="text-xs text-muted leading-relaxed">{item.titleEn}</p>
                  <p className="text-xs text-muted leading-relaxed mt-2">{item.desc}</p>
                </MallCard>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== AI TOOLS BANNER ===== */}
      <section className="py-12" style={{
        background: "linear-gradient(120deg, #003f46 0%, #00505a 60%, #006773 100%)",
      }}>
        <div className="mx-auto max-w-mall px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-6 h-6 text-gold" />
                <h2 className="text-lg font-black text-white">{t("aiToolbox")}</h2>
                <span className="text-[9px] px-2 py-0.5 bg-gold/20 text-gold rounded-full font-extrabold">
                  {t("aiPowered")}
                </span>
              </div>
              <p className="text-white/50 text-sm">
                {t("aiDesc")}
              </p>
            </div>
            <Link
              href="/ai"
              className="px-6 py-2.5 font-extrabold rounded-[10px] text-sm hover:brightness-110 transition flex items-center gap-2 flex-shrink-0 text-white"
              style={{
                background: "linear-gradient(135deg, #f0b734, #e3a615, #c1850b)",
                boxShadow: "0 10px 24px rgba(193,133,11,.4)",
              }}
            >
              {t("aiEnter")} <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="py-14" style={{
        background: "linear-gradient(120deg, #003f46 0%, #00505a 60%, #006773 100%)",
      }}>
        <div className="mx-auto max-w-mall px-6 text-center">
          <h2 className="text-2xl font-black text-white mb-3">{t("ctaTitle")}</h2>
          <p className="text-white/50 text-sm mb-6">
            {t("ctaDesc")}
          </p>
          <div className="flex justify-center gap-3">
            <Link
              href="/register"
              className="px-8 py-3 font-extrabold rounded-[10px] text-sm text-white transition-all hover:-translate-y-0.5"
              style={{
                background: "linear-gradient(135deg, #f0b734, #e3a615, #c1850b)",
                boxShadow: "0 10px 24px rgba(193,133,11,.4)",
              }}
            >
              {t("ctaRegister")}
            </Link>
            <DisabledCta
              title="关于页面待上线"
              className="px-8 py-3 rounded-[10px] text-sm font-extrabold text-white"
            >
              <span style={{ background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.24)", borderRadius: 10, padding: "12px 32px" }}>
                {t("ctaLearnMore")}
              </span>
            </DisabledCta>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
