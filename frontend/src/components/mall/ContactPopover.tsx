"use client";

import { useState, useRef, useEffect, useLayoutEffect, useCallback, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { MessageCircle, Star, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useWhatsApp, useContactInfo } from "@/hooks/useWhatsApp";
import { WeChatIcon } from "@/components/icons/WeChatIcon";
import type { WhatsAppContext } from "@/hooks/useWhatsApp";

/**
 * 联系方式 Popover — 桌面端从按钮右侧弹出气泡，移动端底部抽屉。
 *
 * 无表头，仅 WhatsApp + WeChat 两行。
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
  const [isMobile, setIsMobile] = useState(false);

  // 检测移动端
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // 桌面端：计算位置（按钮右侧、垂直居中）
  useLayoutEffect(() => {
    if (!open || isMobile || !triggerRef.current || !popoverRef.current) {
      setPos(null);
      return;
    }
    const rect = triggerRef.current.getBoundingClientRect();
    const popH = popoverRef.current.offsetHeight;
    const popW = popoverRef.current.offsetWidth;

    let top = rect.top + rect.height / 2 - popH / 2 + window.scrollY;
    let left = rect.right + 8 + window.scrollX;

    // 右侧溢出屏幕 → 改为左侧弹出
    if (left + popW > window.innerWidth - 16) {
      left = rect.left - popW - 8 + window.scrollX;
    }
    // 上下溢出 → 钳制
    top = Math.max(8 + window.scrollY, Math.min(top, window.innerHeight - popH - 8 + window.scrollY));

    setPos({ top, left });
  }, [open, isMobile]);

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

  const close = useCallback(() => setOpen(false), []);

  // 渠道列表（和悬浮面板统一样式）
  const channelList = (
    <div className="space-y-1.5">
      {contact.isLoading ? (
        /* 骨架屏 — 数据加载中 */
        <>
          <div className="flex items-center gap-2 rounded-lg p-2 bg-gray-100 animate-pulse">
            <span className="w-8 h-8 rounded-full bg-gray-200 shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 w-20 bg-gray-200 rounded" />
              <div className="h-2.5 w-32 bg-gray-200 rounded" />
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-lg p-2 bg-gray-50 animate-pulse">
            <span className="w-8 h-8 rounded-full bg-gray-200 shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 w-16 bg-gray-200 rounded" />
              <div className="h-2.5 w-28 bg-gray-200 rounded" />
            </div>
          </div>
        </>
      ) : (
        <>
          {/* WhatsApp — 推荐 */}
          {wa.configured && (
            <a
              href={wa.buildLink(context)!}
              target="_blank"
              rel="noopener noreferrer"
              onClick={close}
              className="flex items-center gap-2 rounded-lg p-2 text-white transition-colors"
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

          {/* WeChat */}
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
        </>
      )}
    </div>
  );

  return (
    <>
      <div ref={triggerRef} className="inline-flex" onClick={() => setOpen((v) => !v)}>
        {children}
      </div>

      {open && createPortal(
        isMobile ? (
          /* 移动端：底部抽屉 */
          <>
            <div className="fixed inset-0 z-[250] bg-black/30" onClick={close} />
            <div className="fixed bottom-0 left-0 right-0 z-[251] bg-white rounded-t-2xl shadow-2xl p-4 pb-6 animate-in slide-in-from-bottom duration-200">
              <div className="w-10 h-1 rounded-full bg-gray-300 mx-auto mb-3" />
              {channelList}
            </div>
          </>
        ) : (
          /* 桌面端：右侧气泡 */
          <div
            ref={popoverRef}
            className="fixed z-[250] transition-opacity duration-150"
            style={{
              top: pos?.top ?? -9999,
              left: pos?.left ?? -9999,
              opacity: pos ? 1 : 0,
            }}
          >
            <div className="w-[260px] rounded-2xl bg-white shadow-lg border border-line overflow-hidden">
              <div className="bg-teal-800 px-3 py-2 flex items-center justify-between">
                <p className="text-white text-[13px] font-bold">{t("consultantTitle")}</p>
                <button onClick={close} className="text-white/60 hover:text-white transition-colors">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="p-2">
              {channelList}
              </div>
            </div>
          </div>
        ),
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
