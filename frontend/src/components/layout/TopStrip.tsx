"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Globe, ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";

const LOCALES = [
  { code: "zh", short: "中", full: "中文", pref: "zh-CN" },
  { code: "en", short: "EN", full: "English", pref: "en" },
  { code: "sw", short: "SW", full: "Kiswahili", pref: "sw-TZ" },
] as const;

/** 顶部深青公告条 + 内嵌语言切换（深色风格）。参考 HTML .top-strip */
export function TopStrip() {
  const t = useTranslations("mall");
  const locale = useLocale();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const fireLanguagePref = (pref: string) => {
    if (!user) return;
    api.patch("/api/v1/auth/me/language", { language_preference: pref }).catch(() => {});
  };

  const current = LOCALES.find((l) => l.code === locale) ?? LOCALES[0];

  return (
    <div className="relative z-[70] bg-teal-950 text-[#cfe6e6] text-[13px]">
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

          {/* 语言切换 — 深色风格 */}
          <div ref={ref} className="relative">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-[#cfe6e6] transition-colors hover:bg-white/10 hover:text-white"
            >
              <Globe className="h-3.5 w-3.5" />
              {current.short}
              <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open && (
              <div className="absolute right-0 z-[999] mt-1 w-40 rounded-lg border border-line bg-white py-1 shadow-mall-lg">
                {LOCALES.map((l) => (
                  <Link
                    key={l.code}
                    href={pathname}
                    locale={l.code}
                    onClick={() => {
                      fireLanguagePref(l.pref);
                      setOpen(false);
                    }}
                    className={`flex items-center justify-between px-3 py-2 text-sm transition-colors ${
                      l.code === locale
                        ? "bg-teal-50 font-medium text-teal-900"
                        : "text-ink hover:bg-teal-50"
                    }`}
                  >
                    <span>{l.short} · {l.full}</span>
                    {l.code === locale && <Check className="h-3.5 w-3.5" />}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
