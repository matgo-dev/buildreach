"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Check, ChevronDown, Globe } from "lucide-react";

import { BRAND } from "@/config/brand";

const LOCALES = [
  { code: "zh" as const, short: "中", full: "中文" },
  { code: "en" as const, short: "EN", full: "English" },
  { code: "sw" as const, short: "SW", full: "Kiswahili" },
];

function AuthLocaleSwitcher() {
  const locale = useLocale();
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
        className="flex items-center gap-1.5 rounded-lg bg-white/15 px-2.5 py-2 text-xs font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/25"
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
                  // 从 window.location.pathname 去掉所有已知 locale 前缀，得到裸路径
                  const currentPath = window.location.pathname;
                  const allCodes = LOCALES.map((x) => x.code);
                  let bare = currentPath;
                  for (const lc of allCodes) {
                    if (bare.startsWith(`/${lc}/`)) {
                      bare = bare.slice(lc.length + 1);
                      break;
                    }
                    if (bare === `/${lc}`) {
                      bare = "/";
                      break;
                    }
                  }
                  // 先显式带上目标 locale，让 next-intl 更新语言偏好；默认语言会再规范化成无前缀路径。
                  const newPath = `/${l.code}${bare === "/" ? "" : bare}`;
                  window.location.href = newPath + window.location.search;
                }
              }}
              className={`flex w-full items-center justify-between px-3 py-2 text-sm transition-colors ${
                l.code === locale
                  ? "bg-teal-50 font-medium text-[#0D4D4D]"
                  : "text-gray-700 hover:bg-teal-50"
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      {/* 背景视频 */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
        poster="/images/home/hero-1.jpg"
      >
        <source src="/uploads/hero-video.mp4" type="video/mp4" />
      </video>
      {/* 深色半透明遮罩（降低视频亮度，让表单突出） */}
      <div className="absolute inset-0 bg-black/60" />

      {/* 语言切换 */}
      <div className="absolute right-4 top-4 z-10">
        <AuthLocaleSwitcher />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* 品牌区 */}
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 shadow-lg backdrop-blur-sm">
            <span className="text-2xl font-black text-white">{BRAND.logoChar}</span>
            <span className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-[#0D4D4D] bg-[#FF6B35]" />
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
