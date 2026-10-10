"use client";
import { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BRAND } from "@/config/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("brand");

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-auto bg-gradient-to-br from-teal-50 via-bg to-teal-100 p-4">
      <div className="relative z-10 w-full max-w-md">
        {/* 品牌区 */}
        <div className="mb-8 text-center">
          <h1>
            <img src={BRAND.logoLockup} alt={t("name")} className="mx-auto h-11 w-auto" />
          </h1>
          <p className="mt-3 text-sm text-muted">{t("tagline")}</p>
        </div>

        {/* 表单卡片 */}
        <div className="rounded-2xl border border-line border-t-4 border-t-lime bg-white p-5 sm:p-8 shadow-mall-lg">
          {children}
        </div>
      </div>
    </div>
  );
}
