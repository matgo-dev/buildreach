"use client";
import { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BRAND } from "@/config/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("brand");

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-auto bg-gradient-to-br from-[#0a2e2e] via-[#0D4D4D] to-[#1a6b6b] p-4">
      <div className="relative z-10 w-full max-w-md">
        {/* 品牌区 */}
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 shadow-lg backdrop-blur-sm overflow-hidden">
            <img src={BRAND.logoMark} alt={BRAND.name} className="h-10 w-10 object-contain" />
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">{t("name")}</h1>
          <p className="mt-2 text-sm text-white/60">{t("tagline")}</p>
        </div>

        {/* 表单卡片 */}
        <div className="rounded-2xl border-t-4 border-[#0D4D4D] bg-white p-8 shadow-xl">
          {children}
        </div>
      </div>
    </div>
  );
}
