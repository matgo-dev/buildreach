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

        {/* 专属客服 — 标题+说明+电话+绿色按钮 */}
        {wa.configured && (
        <MallCard padding="p-3.5">
          <h3 className="text-navy text-base font-black mb-1">{t("customerSupport")}</h3>
          <p className="text-muted text-[13px] mb-3">{t("customerSupportHint")}</p>
          <p className="text-navy text-xl font-black mb-3">{wa.number}</p>
          <MallButton variant="whatsapp" block href={wa.link!}>
            <MessageCircle className="h-4 w-4" />
            {t("chatOnWhatsApp")}
          </MallButton>
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
