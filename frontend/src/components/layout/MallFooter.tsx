"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { MessageCircle, Mail, X } from "lucide-react";
import { BRAND } from "@/config/brand";
import { useContactInfo, useWhatsApp } from "@/hooks/useWhatsApp";
import { WeChatIcon } from "@/components/icons/WeChatIcon";

/** Mall 页脚 — 浅灰绿底四列,深绿标题正文(对齐 intro.matgo.ai 浅色页脚) */
export function MallFooter() {
  const t = useTranslations("mall");
  const contact = useContactInfo();
  const wa = useWhatsApp();
  const [qr, setQr] = useState<"wa" | "wx" | null>(null);

  return (
    <>
      <footer className="bg-teal-50 text-ink-2 border-t border-line mt-2.5">
        <div className="mx-auto max-w-mall px-3 sm:px-6 grid grid-cols-1 md:grid-cols-4 gap-7 pt-8 pb-8">
          {/* 品牌列 */}
          <div className="md:col-span-1">
            <div className="flex items-center gap-1 mb-2.5">
              <img
                src={BRAND.logoLockup}
                alt={BRAND.name}
                className="h-6 w-auto mr-1.5 shrink-0"
              />
              <span className="text-teal-900 text-sm font-bold whitespace-nowrap">
                Material Go 筑达
              </span>
            </div>
            <p className="text-[13px] leading-relaxed text-ink-2">
              {t("footerDescription")}
            </p>
          </div>

          {/* 采购服务 */}
          <div>
            <h4 className="text-teal-900 text-sm font-bold mb-2.5">{t("footerServices")}</h4>
            <div className="space-y-2 text-[13px]">
              <p>{t("footerProductSearch")}</p>
              <p>{t("footerQuoteRequest")}</p>
              <p>{t("footerContainer")}</p>
              <p>{t("footerOrderTracking")}</p>
            </div>
          </div>

          {/* 合规支持 */}
          <div>
            <h4 className="text-teal-900 text-sm font-bold mb-2.5">{t("footerCompliance")}</h4>
            <div className="space-y-2 text-[13px]">
              <p>PVoC / CoC</p>
              <p>Product Certification</p>
              <p>Import Permits</p>
            </div>
          </div>

          {/* 联系方式 */}
          <div>
            <h4 className="text-teal-900 text-sm font-bold mb-2.5">{t("footerContact")}</h4>
            <div className="space-y-2 text-[13px]">
              {contact.whatsappNumber && (
                <p className="flex items-center gap-1.5">
                  <MessageCircle className="w-3.5 h-3.5 shrink-0" />
                  {wa.configured ? (
                    <a
                      href={wa.buildLink()!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-teal-900 hover:underline transition-colors"
                    >
                      {contact.whatsappNumber}
                    </a>
                  ) : (
                    contact.whatsappNumber
                  )}
                  {contact.whatsappQrImage && (
                    <button onClick={() => setQr("wa")} className="ml-1 shrink-0 rounded border border-line bg-white hover:border-teal-400 transition-colors" title={t("wechatScanQr")}>
                      <img src={contact.whatsappQrImage} alt="WhatsApp QR" className="w-8 h-8 object-contain" />
                    </button>
                  )}
                </p>
              )}
              {contact.wechatId && (
                <p className="flex items-center gap-1.5">
                  <WeChatIcon className="w-3.5 h-3.5 shrink-0" />
                  {contact.wechatQrImage ? (
                    <button
                      onClick={() => setQr("wx")}
                      className="hover:text-teal-900 hover:underline transition-colors"
                    >
                      {contact.wechatId}
                    </button>
                  ) : (
                    <span>{contact.wechatId}</span>
                  )}
                  {contact.wechatQrImage && (
                    <button onClick={() => setQr("wx")} className="ml-1 shrink-0 rounded border border-line bg-white hover:border-teal-400 transition-colors" title={t("wechatScanQr")}>
                      <img src={contact.wechatQrImage} alt="WeChat QR" className="w-8 h-8 object-contain" />
                    </button>
                  )}
                </p>
              )}
              {contact.email && (
                <p className="flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 shrink-0" />
                  <a
                    href={`mailto:${contact.email}`}
                    className="hover:text-teal-900 hover:underline transition-colors"
                  >
                    {contact.email}
                  </a>
                </p>
              )}
            </div>
          </div>
        </div>

        {/* 底部版权 */}
        <div className="border-t border-line py-3.5 px-6 text-center text-[12px] text-muted">
          © {new Date().getFullYear()} MATMART COMPANY LIMITED. All rights reserved.
        </div>
      </footer>

      {/* 二维码弹窗(WhatsApp / WeChat 共用,一次只看一个) */}
      {qr && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/50"
          onClick={() => setQr(null)}
        >
          <div
            className="relative bg-white rounded-2xl p-6 shadow-2xl max-w-xs w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setQr(null)}
              className="absolute top-3 right-3 text-muted hover:text-ink-2 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-3">
                {qr === "wa" ? (
                  <MessageCircle className="w-6 h-6 text-[#25d366]" />
                ) : (
                  <WeChatIcon className="w-6 h-6 text-[#07c160]" />
                )}
                <h3 className="text-lg font-bold text-gray-900">{qr === "wa" ? "WhatsApp" : "WeChat"}</h3>
              </div>
              <img
                src={(qr === "wa" ? contact.whatsappQrImage : contact.wechatQrImage) ?? ""}
                alt={qr === "wa" ? "WhatsApp QR Code" : "WeChat QR Code"}
                className="w-56 h-auto mx-auto rounded-lg border border-gray-100"
              />
              {(qr === "wa" ? contact.whatsappContactName : contact.wechatContactName) && (
                <p className="mt-3 text-sm font-semibold text-ink">
                  {qr === "wa" ? contact.whatsappContactName : contact.wechatContactName}
                  <span className="ml-1.5 font-normal text-muted">· {t("contactRole")}</span>
                </p>
              )}
              <p className="mt-1 text-sm text-muted">{qr === "wa" ? contact.whatsappNumber : contact.wechatId}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
