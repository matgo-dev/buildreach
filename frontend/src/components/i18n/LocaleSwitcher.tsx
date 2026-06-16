"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check, ChevronDown, Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";

interface Props {
  /** compact: 图标+简称+三选 popover(header 用);full: 三文字链接(登录页底部用) */
  variant?: "compact" | "full";
}

const LOCALES = [
  { code: "zh", short: "中", full: "中文", pref: "zh-CN" },
  { code: "en", short: "EN", full: "English", pref: "en" },
  { code: "sw", short: "SW", full: "Kiswahili", pref: "sw-TZ" },
] as const;

export function LocaleSwitcher({ variant = "compact" }: Props) {
  const locale = useLocale();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // 切语言时保留 query params(如 ?items=4,5)
  const qs = searchParams.toString();
  const hrefWithQuery = qs ? `${pathname}?${qs}` : pathname;
  const user = useAuthStore((s) => s.user);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭
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

  if (variant === "full") {
    return (
      <span className="flex items-center gap-1 text-xs text-gray-400">
        {LOCALES.map((l, i) => (
          <span key={l.code} className="inline-flex items-center">
            {i > 0 && <span className="mx-1">·</span>}
            {l.code === locale ? (
              <span className="font-semibold text-gray-600">{l.full}</span>
            ) : (
              <Link
                href={hrefWithQuery}
                locale={l.code}
                onClick={() => fireLanguagePref(l.pref)}
                className="transition-colors hover:text-gray-600"
              >
                {l.full}
              </Link>
            )}
          </span>
        ))}
      </span>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-800"
      >
        <Globe className="h-3.5 w-3.5" />
        {current.short}
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-1 w-36 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {LOCALES.map((l) => (
            <Link
              key={l.code}
              href={hrefWithQuery}
              locale={l.code}
              onClick={() => {
                fireLanguagePref(l.pref);
                setOpen(false);
              }}
              className={`flex items-center justify-between px-3 py-2 text-sm transition-colors ${
                l.code === locale
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span>
                {l.short} · {l.full}
              </span>
              {l.code === locale && <Check className="h-3.5 w-3.5" />}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
