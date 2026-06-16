"use client";

import { ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";

/** 顶部深青公告条 — 纯信息展示，滚动后消失。参考 HTML .top-strip */
export function TopStrip() {
  const t = useTranslations("mall");

  return (
    <div className="bg-teal-950 text-[#cfe6e6] text-[13px]">
      <div className="mx-auto max-w-mall px-6 flex items-center justify-between min-h-[36px]">
        <span className="hidden md:inline">
          {t("stripAnnouncement")}
        </span>
        <div className="flex items-center gap-3 text-xs whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-whatsapp/20 px-3 py-0.5 text-[#9af0bc] font-extrabold">
            <ShieldCheck className="h-3.5 w-3.5" />
            PVoC / CoC Document Support
          </span>
          <span className="hidden sm:inline">{t("helpCenter")}</span>
        </div>
      </div>
    </div>
  );
}
