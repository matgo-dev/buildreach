"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { Check, ChevronDown, Globe } from "lucide-react";

import { BRAND } from "@/config/brand";

const LOCALES = [
  { code: "zh" as const, short: "中", full: "中文" },
  { code: "en" as const, short: "EN", full: "English" },
  { code: "sw" as const, short: "SW", full: "Kiswahili" },
];

function AuthLocaleSwitcher() {
  const locale = useLocale();
  const rawPathname = usePathname();
  const router = useRouter();
  // 去掉 locale 前缀
  const pathWithoutLocale = rawPathname.replace(new RegExp(`^/${locale}`), "") || "/";
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const current = LOCALES.find((l) => l.code === locale) ?? LOCALES[0];

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white"
      >
        <Globe className="h-4 w-4" />
        {current.short}
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 z-[200] mt-1 w-40 rounded-lg border border-white/10 bg-white py-1 shadow-xl">
          {LOCALES.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => {
                setOpen(false);
                if (l.code !== locale) {
                  // 直接替换 URL locale 前缀，不触发 React 状态重置
                  const newPath = l.code === "zh" ? pathWithoutLocale : `/${l.code}${pathWithoutLocale}`;
                  router.replace(newPath);
                }
              }}
              className={`flex w-full items-center justify-between px-3 py-2 text-sm transition-colors ${
                l.code === locale
                  ? "bg-blue-50 font-medium text-[#003366]"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <span>{l.short} · {l.full}</span>
              {l.code === locale && <Check className="h-3.5 w-3.5" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AuthLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("brand");

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-[#003366] to-[#0F4C81] p-4">
      {/* 语言切换 */}
      <div className="absolute right-4 top-4">
        <AuthLocaleSwitcher />
      </div>

      <div className="w-full max-w-md">
        {/* 品牌区:品牌名不翻译,tagline 跟随语言 */}
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#003366] to-[#0F4C81] shadow-lg">
            <span className="text-2xl font-black text-white">{BRAND.logoChar}</span>
            <span className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-[#003366] bg-[#FF6B35]" />
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">{t("name")}</h1>
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
