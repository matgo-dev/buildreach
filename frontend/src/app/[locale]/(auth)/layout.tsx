"use client";
import { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BRAND } from "@/config/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("brand");

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-auto bg-gradient-to-b from-[#FFF8E6] via-white to-bg p-4">
      {/* 与商城首页同一张建筑氛围图,铺在顶部;再加一团很淡的暖黄光晕托住表单 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[480px] bg-[url(/images/bg-top.png)] bg-[length:1536px_480px] bg-[position:center_top] bg-no-repeat"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 h-[560px] w-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(255,194,14,.16),transparent)]"
      />
      <div className="relative z-10 w-full max-w-md">
        {/* 品牌区 */}
        <div className="mb-8 text-center">
          <h1>
            <img src={BRAND.logoLockup} alt={t("name")} className="mx-auto h-12 w-auto" />
          </h1>
          <p className="mt-3 text-sm text-muted">{t("tagline")}</p>
        </div>

        {/* 表单卡片 */}
        <div className="rounded-2xl border border-line bg-white/95 p-5 sm:p-8 shadow-[0_20px_50px_-20px_rgba(31,35,40,.25)] backdrop-blur">
          {children}
        </div>
      </div>
    </div>
  );
}
