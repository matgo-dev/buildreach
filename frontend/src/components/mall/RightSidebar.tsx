"use client";

import { useTranslations } from "next-intl";
import { MessageCircle, ShieldCheck, FileCheck, CreditCard, Truck } from "lucide-react";
import { useCartStore } from "@/stores/cartStore";
import { useWhatsApp } from "@/hooks/useWhatsApp";
import { MallButton } from "./MallButton";
import { MallCard } from "./MallCard";

/**
 * 商城右侧栏 — WhatsApp 客服 + RFQ 购物车摘要。
 */
export function RightSidebar() {
  const t = useTranslations("mall");
  const cartCount = useCartStore((s) => s.count);
  const wa = useWhatsApp();

  return (
    <aside className="w-[300px] shrink-0 hidden xl:block">
      <div className="sticky top-[148px] space-y-3.5">
        {/* 专属客服 — 号码未配置时隐藏整个卡片 */}
        {wa.configured && (
        <MallCard>
          <h3 className="text-navy text-base font-black mb-1">{t("customerSupport")}</h3>
          <p className="text-muted text-[13px] mb-3">{t("customerSupportHint")}</p>
          <p className="text-navy text-xl font-black mb-3">{wa.number}</p>
          <MallButton
            variant="whatsapp"
            block
            href={wa.link!}
          >
            <MessageCircle className="h-4 w-4" />
            {t("chatOnWhatsApp")}
          </MallButton>
        </MallCard>
        )}

        {/* 询价单 RFQ Cart */}
        <MallCard>
          <h3 className="text-navy text-base font-black mb-1">{t("rfqCart")}</h3>
          <p className="text-muted text-xs mb-3">{t("rfqCartHint")}</p>
          <div className="rounded-lg bg-[#f7fafb] border border-[#e4edf2] p-3 mb-3">
            <div className="flex justify-between text-xs text-muted">
              <span>{t("rfqItems")}</span>
              <strong className="text-navy">{cartCount}</strong>
            </div>
          </div>
          <MallButton variant="teal" block href="/buyer/cart">
            {t("submitRfq")}
          </MallButton>
        </MallCard>

        {/* Trust Marks */}
        <MallCard>
          <p className="text-navy text-sm font-black mb-3">{t("trustMarks")}</p>
          <ul className="space-y-2.5">
            {[
              { icon: ShieldCheck, title: t("trustVerified"), desc: t("trustVerifiedDesc") },
              { icon: FileCheck,   title: t("trustCertified"), desc: t("trustCertifiedDesc") },
              { icon: CreditCard,  title: t("trustPrice"),    desc: t("trustPriceDesc") },
              { icon: Truck,       title: t("trustDelivery"), desc: t("trustDeliveryDesc") },
            ].map(({ icon: Icon, title, desc }) => (
              <li key={title} className="grid grid-cols-[24px_1fr] gap-2.5 items-start">
                <span className="w-6 h-6 rounded-full grid place-items-center text-whatsapp" style={{ background: "#e5f7ee" }}>
                  <Icon className="h-3 w-3" />
                </span>
                <span>
                  <strong className="block text-[13px] text-navy mb-0.5">{title}</strong>
                  <span className="text-xs text-muted leading-snug">{desc}</span>
                </span>
              </li>
            ))}
          </ul>
        </MallCard>
      </div>
    </aside>
  );
}
