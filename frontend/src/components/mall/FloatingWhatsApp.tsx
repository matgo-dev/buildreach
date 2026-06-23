"use client";

import { useState } from "react";
import { MessageCircle, X, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useWhatsApp } from "@/hooks/useWhatsApp";

/**
 * 底部悬浮 WhatsApp 入口 — 紧凑胶囊按钮。
 *
 * 收起态：小胶囊，WhatsApp 图标 + 文字，不遮挡主内容。
 * 展开态：向上弹出客服卡片。
 */
export function FloatingWhatsApp() {
  const t = useTranslations("mall");
  const wa = useWhatsApp();
  const [open, setOpen] = useState(false);

  if (!wa.configured) return null;

  return (
    <>
      {/* 展开态背景遮罩 */}
      {open && (
        <div
          className="fixed inset-0 z-[199]"
          onClick={() => setOpen(false)}
        />
      )}

      <div className="fixed bottom-5 right-5 z-[200] flex flex-col items-end gap-2.5">
        {/* 展开卡片 — 向上弹出 */}
        {open && (
          <div className="w-[300px] rounded-2xl bg-white shadow-mall-lg border border-line overflow-hidden">
            {/* 卡片头 */}
            <div className="bg-[#075e54] px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-white text-sm font-bold">{t("floatWaTitle")}</p>
                <p className="text-white/70 text-xs">{t("floatWaHint")}</p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-white/60 hover:text-white transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* 客服入口 */}
            <div className="p-4">
              <a
                href={wa.link!}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-xl bg-[#f0f2f5] p-3.5 hover:bg-[#e4e6eb] transition-colors"
              >
                <span className="w-11 h-11 rounded-full bg-whatsapp grid place-items-center shrink-0 shadow-sm">
                  <MessageCircle className="h-5 w-5 text-white" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-navy">{t("floatWaAgent")}</p>
                  <p className="text-xs text-muted">{wa.number}</p>
                </div>
                <ChevronRight className="h-4 w-4 text-muted shrink-0" />
              </a>

              {/* 引导文案 */}
              <div className="mt-3 rounded-lg bg-teal-50 px-3 py-2.5">
                <p className="text-[12px] font-semibold text-teal-900">{t("floatWaCta")}</p>
                <p className="text-[11px] text-teal-800/70 mt-0.5">{t("floatWaCtaHint")}</p>
              </div>
            </div>
          </div>
        )}

        {/* 胶囊按钮 */}
        <button
          onClick={() => setOpen((v) => !v)}
          className={`group flex items-center gap-2 rounded-full pl-3.5 pr-4 py-2.5 shadow-lg transition-all duration-200 ${
            open
              ? "bg-[#075e54] hover:bg-[#064e47]"
              : "bg-whatsapp hover:bg-[#20bd5a] hover:shadow-xl hover:scale-105"
          }`}
        >
          {open ? (
            <X className="h-4.5 w-4.5 text-white" />
          ) : (
            <MessageCircle className="h-5 w-5 text-white" />
          )}
          <span className="text-[13px] font-bold text-white whitespace-nowrap">
            {open ? t("floatWaClose") : t("floatWaTab")}
          </span>
        </button>
      </div>
    </>
  );
}
