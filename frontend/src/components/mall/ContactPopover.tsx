"use client";

import { useState, useRef, useEffect, useLayoutEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { MessageCircle, Star, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useWhatsApp, useContactInfo } from "@/hooks/useWhatsApp";
import { WeChatIcon } from "@/components/icons/WeChatIcon";
import type { WhatsAppContext } from "@/hooks/useWhatsApp";

/**
 * 联系方式 Popover — 从触发按钮右侧弹出气泡。
 *
 * 无表头，仅 WhatsApp + WeChat 两行，淡入淡出。
 * 点击外部自动关闭。
 */
export function ContactPopover({
  children,
  context,
}: {
  children: ReactNode;
  context?: WhatsAppContext;
}) {
  const t = useTranslations("mall");
  const wa = useWhatsApp();
  const contact = useContactInfo();
  const [open, setOpen] = useState(false);
  const [showQr, setShowQr] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  // 计算位置：按钮右侧、垂直居中，用 layoutEffect 避免闪烁
  useLayoutEffect(() => {
    if (!open || !triggerRef.current || !popoverRef.current) {
      setPos(null);
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    const popH = popoverRef.current.offsetHeight;
    setPos({
      top: rect.top + rect.height / 2 - popH / 2 + window.scrollY,
      left: rect.right + 8 + window.scrollX,
    });
  }, [open]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        triggerRef.current?.contains(e.target as Node) ||
        popoverRef.current?.contains(e.target as Node)
      ) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <>
      <div ref={triggerRef} className="inline-flex" onClick={() => setOpen((v) => !v)}>
        {children}
      </div>

      {/* Popover 气泡 */}
      {open && createPortal(
        <div
          ref={popoverRef}
          className="fixed z-[250] transition-opacity duration-150"
          style={{
            top: pos?.top ?? -9999,
            left: pos?.left ?? -9999,
            opacity: pos ? 1 : 0,
          }}
        >
          <div className="w-[220px] rounded-xl bg-white shadow-lg border border-gray-200 p-1.5 space-y-1">
            {/* WhatsApp */}
            {wa.configured && (
              <a
                href={wa.buildLink(context)!}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-lg p-2 text-white transition-colors"
                style={{ background: "linear-gradient(135deg, #2bd86e, #1aa851)" }}
              >
                <span className="w-7 h-7 rounded-full bg-white/20 grid place-items-center shrink-0">
                  <MessageCircle className="h-3.5 w-3.5 text-white" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1">
                    <span className="text-[12px] font-bold">WhatsApp</span>
                    <span className="inline-flex items-center gap-0.5 text-[8px] bg-white/25 rounded-full px-1 py-px font-medium">
                      <Star className="h-1.5 w-1.5 fill-current" />
                      {t("recommended")}
                    </span>
                  </div>
                </div>
              </a>
            )}

            {/* WeChat */}
            {contact.wechatId && (
              <button
                onClick={() => { setShowQr(true); setOpen(false); }}
                className="w-full flex items-center gap-2 rounded-lg border border-gray-100 bg-white p-2 hover:bg-gray-50 transition-colors text-left"
              >
                <span className="w-7 h-7 rounded-full bg-[#07c160]/10 grid place-items-center shrink-0">
                  <WeChatIcon className="h-3.5 w-3.5 text-[#07c160]" />
                </span>
                <span className="text-[12px] font-bold text-navy">WeChat</span>
              </button>
            )}
          </div>
        </div>,
        document.body,
      )}

      {/* WeChat QR 码弹窗 */}
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
