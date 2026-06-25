"use client";

import { useTranslations } from "next-intl";
import { MessageCircle, Mail } from "lucide-react";
import { BRAND } from "@/config/brand";
import { useWhatsApp } from "@/hooks/useWhatsApp";

/** Mall 页脚 — 深青底色四列。参考 HTML footer */
export function MallFooter() {
  const t = useTranslations("mall");
  const wa = useWhatsApp();

  return (
    <footer className="bg-teal-950 text-[#d6eded] mt-2.5">
      <div className="mx-auto max-w-mall px-3 sm:px-6 grid grid-cols-1 md:grid-cols-4 gap-7 pt-8 pb-8">
        {/* 品牌列 */}
        <div className="md:col-span-1">
          <h3 className="text-white text-base font-black mb-2.5">{BRAND.name}</h3>
          <p className="text-[13px] leading-relaxed text-[#d6eded]">
            {BRAND.description}
          </p>
        </div>

        {/* 采购服务 */}
        <div>
          <h4 className="text-white text-sm font-bold mb-2.5">{t("footerServices")}</h4>
          <div className="space-y-2 text-[13px]">
            <p>{t("footerProductSearch")}</p>
            <p>{t("footerQuoteRequest")}</p>
            <p>{t("footerContainer")}</p>
            <p>{t("footerOrderTracking")}</p>
          </div>
        </div>

        {/* 合规支持 */}
        <div>
          <h4 className="text-white text-sm font-bold mb-2.5">{t("footerCompliance")}</h4>
          <div className="space-y-2 text-[13px]">
            <p>PVoC / CoC</p>
            <p>TBS Standards</p>
            <p>KEBS Certification</p>
            <p>Import Permits</p>
          </div>
        </div>

        {/* 联系方式 */}
        <div>
          <h4 className="text-white text-sm font-bold mb-2.5">{t("footerContact")}</h4>
          <div className="space-y-2 text-[13px]">
            {wa.number && (
              <p className="flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5 shrink-0" />
                {wa.number}
              </p>
            )}
            <p className="flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 shrink-0" />
              info@buildreach.co.tz
            </p>
          </div>
        </div>
      </div>

      {/* 底部版权 */}
      <div className="border-t border-white/10 py-3.5 px-6 text-center text-[12px] text-[#b4d7d5]">
        © {new Date().getFullYear()} BuildReach. All rights reserved.
      </div>
    </footer>
  );
}
