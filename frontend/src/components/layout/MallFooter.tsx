"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { MessageCircle, Mail, X } from "lucide-react";
import { BRAND } from "@/config/brand";
import { useContactInfo } from "@/hooks/useWhatsApp";
import { WeChatIcon } from "@/components/icons/WeChatIcon";

/** Mall 页脚 — 深青底色四列。参考 HTML footer */
export function MallFooter() {
  const t = useTranslations("mall");
  const contact = useContactInfo();
  const [showQr, setShowQr] = useState(false);

  return (
    <>
      <footer className="relative overflow-hidden bg-teal-900 text-[#d6eded] mt-2.5">
        {/* 品类总览大图 — 按比例完整、清晰显示;下部渐隐到绿承托文字,文字上移压在图下部使整体更紧凑 */}
        <div className="relative w-full">
          <div
            aria-hidden
            className="w-full bg-cover bg-center bg-no-repeat"
            style={{
              aspectRatio: "1440 / 490",
              backgroundImage: "url('/footer/materials-band.webp')",
            }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "linear-gradient(to bottom, transparent 0%, transparent 70%, rgba(14,80,56,0.9) 85%, #0e5038 93%)",
            }}
          />
        </div>

        <div className="relative -mt-[4vw] mx-auto max-w-mall px-3 sm:px-6 grid grid-cols-1 md:grid-cols-4 gap-7 pb-8">
          {/* 品牌列 */}
          <div className="md:col-span-1">
            <div className="flex items-center gap-1 mb-2.5">
              <img
                src={BRAND.logoLockupDark}
                alt={BRAND.name}
                className="h-8 w-auto -my-1.5 shrink-0"
              />
              <span className="text-white text-sm font-bold whitespace-nowrap">
                Material Go 筑达
              </span>
            </div>
            <p className="text-[13px] leading-relaxed text-[#d6eded]">
              {t("footerDescription")}
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
              {contact.whatsappNumber && (
                <p className="flex items-center gap-1.5">
                  <MessageCircle className="w-3.5 h-3.5 shrink-0" />
                  {contact.whatsappNumber}
                </p>
              )}
              {contact.wechatId && (
                <p className="flex items-center gap-1.5">
                  <WeChatIcon className="w-3.5 h-3.5 shrink-0" />
                  <span>{contact.wechatId}</span>
                  {contact.wechatQrImage && (
                    <button
                      onClick={() => setShowQr(true)}
                      className="ml-1.5 shrink-0 rounded border border-white/20 hover:border-white/50 transition-colors overflow-hidden"
                      title={t("wechatScanQr")}
                    >
                      <img
                        src={contact.wechatQrImage}
                        alt="WeChat QR"
                        className="w-7 h-7 object-cover"
                      />
                    </button>
                  )}
                </p>
              )}
              {contact.email && (
                <p className="flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 shrink-0" />
                  {contact.email}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* 底部版权 */}
        <div className="relative border-t border-white/10 py-3.5 px-6 text-center text-[12px] text-[#b4d7d5]">
          © {new Date().getFullYear()} Matgo. All rights reserved.
        </div>
      </footer>

      {/* WeChat QR 码弹窗 */}
      {showQr && contact.wechatQrImage && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/50"
          onClick={() => setShowQr(false)}
        >
          <div
            className="relative bg-white rounded-2xl p-6 shadow-2xl max-w-xs w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowQr(false)}
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-3">
                <WeChatIcon className="w-6 h-6 text-[#07c160]" />
                <h3 className="text-lg font-bold text-gray-900">{t("wechatAddUs")}</h3>
              </div>
              <img
                src={contact.wechatQrImage}
                alt="WeChat QR Code"
                className="w-52 h-52 mx-auto rounded-lg border border-gray-100"
              />
              {contact.wechatId && (
                <p className="mt-3 text-sm text-gray-500">
                  {t("wechatIdLabel")}: <span className="font-mono text-gray-700">{contact.wechatId}</span>
                </p>
              )}
              <p className="mt-2 text-xs text-gray-400">{t("wechatScanHint")}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
