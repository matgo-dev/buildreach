"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";
import { routing } from "@/i18n/routing";

interface Props {
  /** compact: 图标+简称+三选 popover(header 用);full: 三文字链接(登录页底部用) */
  variant?: "compact" | "full";
}

const LOCALES = [
  { code: "zh", short: "中", full: "中文", pref: "zh-CN" },
  { code: "en", short: "EN", full: "English", pref: "en" },
  { code: "sw", short: "SW", full: "Kiswahili", pref: "sw-TZ" },
] as const;

/**
 * 构建切语言后的完整 URL（保留 query params + hash）。
 *
 * localePrefix="as-needed" 规则：
 *   默认语言(zh)不带前缀: /buyer/rfqs/create?items=4,5
 *   非默认语言带前缀:     /en/buyer/rfqs/create?items=4,5
 */
function buildLocalizedUrl(targetLocale: string): string {
  const { pathname, search, hash } = window.location;
  const defaultLocale = routing.defaultLocale; // "zh"
  const locales = routing.locales as readonly string[];

  // 去掉当前 locale 前缀，得到裸路径
  let bare = pathname;
  for (const loc of locales) {
    const prefix = `/${loc}`;
    if (bare === prefix || bare.startsWith(`${prefix}/`)) {
      bare = bare.slice(prefix.length) || "/";
      break;
    }
  }

  // 拼目标前缀
  const newPath =
    targetLocale === defaultLocale ? bare : `/${targetLocale}${bare}`;

  return `${newPath}${search}${hash}`;
}

export function LocaleSwitcher({ variant = "compact" }: Props) {
  const locale = useLocale();
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

  // 切语言：设 cookie 让 middleware 识别 + 硬跳转
  const switchLocale = useCallback(
    (targetLocale: string, pref: string) => {
      if (targetLocale === locale) return;
      // 必须在跳转前设置 NEXT_LOCALE cookie，否则 middleware 会按旧偏好重定向回来
      document.cookie = `NEXT_LOCALE=${targetLocale};path=/;max-age=31536000;SameSite=Lax`;
      fireLanguagePref(pref);
      window.location.href = buildLocalizedUrl(targetLocale);
    },
    [locale],
  );

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
              <button
                type="button"
                onClick={() => switchLocale(l.code, l.pref)}
                className="transition-colors hover:text-gray-600"
              >
                {l.full}
              </button>
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
            <button
              key={l.code}
              type="button"
              onClick={() => {
                switchLocale(l.code, l.pref);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between px-3 py-2 text-sm transition-colors ${
                l.code === locale
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span>
                {l.short} · {l.full}
              </span>
              {l.code === locale && <Check className="h-3.5 w-3.5" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
