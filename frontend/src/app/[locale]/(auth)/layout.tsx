"use client";
import { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BRAND } from "@/config/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("brand");

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#003366] to-[#0F4C81] p-4">
      <div className="w-full max-w-md">
        {/* 品牌区:品牌名不翻译,tagline 跟随语言 */}
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#003366] to-[#0F4C81] shadow-lg">
            <span className="text-2xl font-black text-white">{BRAND.logoChar}</span>
            <span className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-[#003366] bg-[#FF6B35]" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">{BRAND.name}</h1>
          <p className="mt-1 text-[10px] tracking-[0.2em] text-white/40">{BRAND.nameEn}</p>
          <p className="mt-2 text-sm text-white/60">{t("tagline")}</p>
        </div>

        {/* 表单卡片 */}
        <div className="rounded-2xl border-t-4 border-[#FF6B35] bg-white p-8 shadow-xl">
          {children}
        </div>
      </div>
    </div>
  );
}
