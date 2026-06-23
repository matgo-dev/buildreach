"use client";

import { useTranslations } from "next-intl";
import { MessageCircle, ShieldCheck, FileCheck, CreditCard, Truck, UserCircle2 } from "lucide-react";
import { useWhatsApp } from "@/hooks/useWhatsApp";
import { useAuthStore } from "@/stores/authStore";
import { MallButton } from "./MallButton";
import { MallCard } from "./MallCard";

/**
 * 商城右侧栏 — 注册引导 / 客服 / 信任标识。
 *
 * variant:
 * - "home": 首页模式，不 sticky，参与三栏等高
 * - "mall" (默认): 商城列表页，sticky 定位
 */
export function RightSidebar({ variant = "mall" }: { variant?: "home" | "mall" }) {
  const t = useTranslations("mall");
  const wa = useWhatsApp();
  const user = useAuthStore((s) => s.user);
  const loaded = useAuthStore((s) => s.loaded);

  const isSticky = variant === "mall";

  return (
    <aside className={`w-[220px] shrink-0 hidden xl:block ${isSticky ? "" : "self-stretch overflow-hidden"}`}>
      <div className={`space-y-2.5 ${isSticky ? "sticky top-[148px]" : ""}`}>
        {/* 未登录时：注册/登录引导（loaded 前不渲染，避免刷新闪烁） */}
        {loaded && !user && (
        <MallCard padding="p-3">
          <div className="flex items-center gap-2 mb-2.5">
            <UserCircle2 className="w-6 h-6 text-slate-300 shrink-0" />
            <p className="text-navy text-[13px] font-black">{t("welcomeGuest")}</p>
          </div>
          <div className="flex gap-2">
            <MallButton variant="teal" size="sm" block href="/register">
              {t("registerNow")}
            </MallButton>
            <MallButton variant="outline" size="sm" block href="/login">
              {t("signIn")}
            </MallButton>
          </div>
        </MallCard>
        )}

        {/* 专属客服 — 与悬浮卡片同风格 */}
        {wa.configured && (
        <MallCard padding="p-0">
          <div className="bg-[#075e54] px-3.5 py-2.5 rounded-t-xl">
            <p className="text-white text-[13px] font-bold">{t("floatWaTitle")}</p>
            <p className="text-white/70 text-[11px]">{t("floatWaHint")}</p>
          </div>
          <div className="p-3">
            <a
              href={wa.link!}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2.5 rounded-lg bg-[#f0f2f5] p-2.5 hover:bg-[#e4e6eb] transition-colors"
            >
              <span className="w-9 h-9 rounded-full bg-whatsapp grid place-items-center shrink-0">
                <MessageCircle className="h-4 w-4 text-white" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold text-navy">{t("floatWaAgent")}</p>
                <p className="text-[11px] text-muted truncate">{wa.number}</p>
              </div>
            </a>
            <div className="mt-2 rounded-md bg-teal-50 px-2.5 py-2">
              <p className="text-[11px] font-semibold text-teal-900">{t("floatWaCta")}</p>
              <p className="text-[10px] text-teal-800/70 mt-0.5">{t("floatWaCtaHint")}</p>
            </div>
          </div>
        </MallCard>
        )}

        {/* 平台保障 */}
        <MallCard padding="p-3">
          <p className="text-navy text-[13px] font-black mb-2">{t("trustMarks")}</p>
          <ul className="space-y-2">
            {[
              { icon: ShieldCheck, title: t("trustVerified"), desc: t("trustVerifiedDesc") },
              { icon: FileCheck,   title: t("trustCertified"), desc: t("trustCertifiedDesc") },
              { icon: CreditCard,  title: t("trustPrice"),    desc: t("trustPriceDesc") },
              { icon: Truck,       title: t("trustDelivery"), desc: t("trustDeliveryDesc") },
            ].map(({ icon: Icon, title, desc }) => (
              <li key={title} className="grid grid-cols-[20px_1fr] gap-2 items-start">
                <span className="w-5 h-5 rounded-full grid place-items-center text-whatsapp shrink-0" style={{ background: "#e5f7ee" }}>
                  <Icon className="h-2.5 w-2.5" />
                </span>
                <span>
                  <strong className="block text-[12px] text-navy">{title}</strong>
                  <span className="text-[10px] text-muted leading-tight">{desc}</span>
                </span>
              </li>
            ))}
          </ul>
        </MallCard>
      </div>
    </aside>
  );
}
