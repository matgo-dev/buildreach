"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { MessageCircle, X, Headphones, Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useWhatsApp, useContactInfo } from "@/hooks/useWhatsApp";
import { useContactStore } from "@/stores/contactStore";
import { WeChatIcon } from "@/components/icons/WeChatIcon";

/**
 * 悬浮采购顾问入口 — WhatsApp + WeChat 双渠道。
 *
 * 收起态：teal 胶囊按钮。
 * 展开态：渠道选择面板，WhatsApp 推荐 + WeChat 备选。
 * 支持通过自定义事件 "open-contact-panel" 从外部打开。
 */
export function FloatingWhatsApp() {
  const t = useTranslations("mall");
  const wa = useWhatsApp();
  const contact = useContactInfo();
  const [open, setOpen] = useState(false);
  const [showQr, setShowQr] = useState(false);
  const { isOpen: storeOpen, context, close: storeClose } = useContactStore();

  // 其他页面通过 contactStore.open() 触发时，打开悬浮面板
  useEffect(() => {
    if (storeOpen) {
      setOpen(true);
      storeClose();
    }
  }, [storeOpen, storeClose]);

  if (!wa.configured && !contact.wechatId) return null;

  return (
    <>
      {/* 遮罩 */}
      {open && (
        <div
          className="fixed inset-0 z-[199]"
          onClick={() => setOpen(false)}
        />
      )}

      <div className="fixed bottom-5 right-5 z-[200] flex flex-col items-end gap-2.5">
        {/* 展开面板 */}
        {open && (
          <div className="w-[260px] rounded-2xl bg-white shadow-mall-lg border border-line overflow-hidden">
            {/* 头部 */}
            <div className="bg-teal-800 px-3 py-2 flex items-center justify-between">
              <p className="text-white text-[13px] font-bold">{t("consultantTitle")}</p>
              <button
                onClick={() => setOpen(false)}
                className="text-white/60 hover:text-white transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="p-2 space-y-1.5">
              {/* WhatsApp — 推荐 */}
              {wa.configured && (
                <a
                  href={wa.buildLink(context ?? undefined)!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-lg p-2 transition-colors text-white"
                  style={{ background: "linear-gradient(135deg, #2bd86e, #1aa851)" }}
                >
                  <span className="w-8 h-8 rounded-full bg-white/20 grid place-items-center shrink-0">
                    <MessageCircle className="h-4 w-4 text-white" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1">
                      <span className="text-[12px] font-bold">WhatsApp</span>
                      <span className="inline-flex items-center gap-0.5 text-[9px] bg-white/25 rounded-full px-1 py-px font-medium">
                        <Star className="h-2 w-2 fill-current" />
                        {t("recommended")}
                      </span>
                    </div>
                    <p className="text-[10px] text-white/80 leading-tight">{t("floatWaDesc")}</p>
                  </div>
                </a>
              )}

              {/* WeChat — 白底描边 */}
              {contact.wechatId && (
                <button
                  onClick={() => { setShowQr(true); setOpen(false); }}
                  className="w-full flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-2 hover:bg-gray-50 transition-colors text-left"
                >
                  <span className="w-8 h-8 rounded-full bg-[#07c160]/10 grid place-items-center shrink-0">
                    <WeChatIcon className="h-4 w-4 text-[#07c160]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-bold text-navy">WeChat</p>
                    <p className="text-[10px] text-muted leading-tight">{t("floatWeChatDesc")}</p>
                  </div>
                </button>
              )}
            </div>
          </div>
        )}

        {/* 胶囊按钮 */}
        <button
          onClick={() => setOpen((v) => !v)}
          className={`group flex items-center gap-2 rounded-full pl-3.5 pr-4 py-2.5 shadow-lg transition-all duration-200 ${
            open
              ? "bg-teal-800 hover:bg-teal-900"
              : "bg-teal-700 hover:bg-teal-800 hover:shadow-xl hover:scale-105"
          }`}
        >
          {open ? (
            <X className="h-4.5 w-4.5 text-white" />
          ) : (
            <Headphones className="h-5 w-5 text-white" />
          )}
          <span className="text-[13px] font-bold text-white whitespace-nowrap">
            {open ? t("floatWaClose") : t("floatContactTab")}
          </span>
        </button>
      </div>

      {/* WeChat QR 码弹窗 — Portal 到 body */}
      {showQr && contact.wechatQrImage && createPortal(
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
        </div>,
        document.body,
      )}
    </>
  );
}
