"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { X, MessageCircle, ChevronRight, Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useContactStore } from "@/stores/contactStore";
import { useWhatsApp, useContactInfo } from "@/hooks/useWhatsApp";
import { WeChatIcon } from "@/components/icons/WeChatIcon";

/**
 * 全局联系方式弹窗 — WhatsApp + WeChat 双渠道选择。
 *
 * 通过 useContactStore().open() 从任意页面触发。
 * 挂载在 PublicLayout 中，Portal 到 body。
 */
export function ContactModal() {
  const t = useTranslations("mall");
  const { isOpen, context, close } = useContactStore();
  const wa = useWhatsApp();
  const contact = useContactInfo();
  const [showQr, setShowQr] = useState(false);

  if (!isOpen && !showQr) return null;

  const waLink = wa.buildLink(context ?? undefined);

  return createPortal(
    <>
      {/* 渠道选择弹窗 */}
      {isOpen && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/50"
          onClick={close}
        >
          <div
            className="relative bg-white rounded-2xl shadow-2xl w-[340px] max-w-[calc(100vw-2rem)] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 头部 */}
            <div className="bg-teal-800 px-5 py-4 flex items-center justify-between">
              <div>
                <p className="text-white text-[15px] font-bold">{t("consultantTitle")}</p>
                <p className="text-white/70 text-xs mt-0.5">{t("floatContactHint")}</p>
              </div>
              <button
                onClick={close}
                className="text-white/60 hover:text-white transition-colors"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <div className="p-4 space-y-2.5">
              {/* WhatsApp — 推荐 */}
              {wa.configured && (
                <a
                  href={waLink!}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={close}
                  className="flex items-center gap-3 rounded-xl p-3.5 text-white transition-all hover:-translate-y-px"
                  style={{
                    background: "linear-gradient(135deg, #2bd86e, #1aa851)",
                    boxShadow: "0 4px 14px rgba(37,211,102,.3)",
                  }}
                >
                  <span className="w-11 h-11 rounded-full bg-white/20 grid place-items-center shrink-0">
                    <MessageCircle className="h-5 w-5 text-white" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <p className="text-[14px] font-bold">WhatsApp</p>
                      <span className="inline-flex items-center gap-0.5 text-[10px] bg-white/25 rounded-full px-1.5 py-0.5 font-medium">
                        <Star className="h-2.5 w-2.5 fill-current" />
                        {t("recommended")}
                      </span>
                    </div>
                    <p className="text-xs text-white/80 mt-0.5">{t("floatWaDesc")}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-white/60 shrink-0" />
                </a>
              )}

              {/* WeChat — 白底描边 */}
              {contact.wechatId && (
                <button
                  onClick={() => { setShowQr(true); close(); }}
                  className="w-full flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3.5 hover:bg-gray-50 transition-colors text-left"
                >
                  <span className="w-11 h-11 rounded-full bg-[#07c160]/10 grid place-items-center shrink-0">
                    <WeChatIcon className="h-5 w-5 text-[#07c160]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-bold text-navy">WeChat</p>
                    <p className="text-xs text-muted mt-0.5">{t("floatWeChatDesc")}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted shrink-0" />
                </button>
              )}

              {/* 引导文案 */}
              <div className="rounded-lg bg-teal-50 px-3.5 py-2.5">
                <p className="text-[12px] font-semibold text-teal-900">{t("floatWaCta")}</p>
                <p className="text-[11px] text-teal-800/70 mt-0.5">{t("floatWaCtaHint")}</p>
              </div>
            </div>
          </div>
        </div>
      )}

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
    </>,
    document.body,
  );
}
