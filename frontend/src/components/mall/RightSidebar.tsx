"use client";

import { useTranslations } from "next-intl";
import { MessageCircle, ShieldCheck, FileCheck, CreditCard, Truck } from "lucide-react";
import { useWhatsApp } from "@/hooks/useWhatsApp";
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
  const isSticky = variant === "mall";

  return (
    <aside className={`w-[220px] shrink-0 hidden xl:block ${isSticky ? "" : "self-stretch"}`}>
      <div className={isSticky ? "sticky top-[148px] space-y-2" : "flex h-full flex-col gap-2 overflow-hidden"}>

        {/* 专属客服 — 标题+说明+电话+绿色按钮 */}
        {wa.configured && (
        <MallCard padding="p-2.5">
          <h3 className="text-navy text-[15px] font-black mb-0.5">{t("customerSupport")}</h3>
          <p className="text-muted text-[12px] mb-2">{t("customerSupportHint")}</p>
          <p className="text-navy text-lg font-black mb-2">{wa.number}</p>
          <MallButton variant="whatsapp" block href={wa.buildLink()!}>
            <MessageCircle className="h-4 w-4" />
            {t("chatOnWhatsApp")}
          </MallButton>
        </MallCard>
        )}

        {/* 平台保障 — home 模式下拉伸填满剩余空间 */}
        <MallCard padding="p-2.5" className={isSticky ? "" : "flex min-h-0 flex-1 flex-col"}>
          <p className="text-navy text-[13px] font-black mb-1.5">{t("trustMarks")}</p>
          <ul className={isSticky ? "space-y-1.5" : "flex flex-1 flex-col justify-between"}>
            {[
              { icon: ShieldCheck, title: t("trustVerified"), desc: t("trustVerifiedDesc") },
              { icon: FileCheck,   title: t("trustCertified"), desc: t("trustCertifiedDesc") },
              { icon: CreditCard,  title: t("trustPrice"),    desc: t("trustPriceDesc") },
              { icon: Truck,       title: t("trustDelivery"), desc: t("trustDeliveryDesc") },
            ].map(({ icon: Icon, title, desc }) => (
              <li key={title} className="grid grid-cols-[18px_1fr] gap-1.5 items-start">
                <span className="w-[18px] h-[18px] rounded-full grid place-items-center text-whatsapp shrink-0" style={{ background: "#e5f7ee" }}>
                  <Icon className="h-2.5 w-2.5" />
                </span>
                <span>
                  <strong className="block text-[11px] text-navy leading-tight">{title}</strong>
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
