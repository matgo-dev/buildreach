"use client";
import { Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";

interface Props {
  /** compact: 仅图标+简称(header 用);full: 完整文字(登录页底部用) */
  variant?: "compact" | "full";
}

export function LocaleSwitcher({ variant = "compact" }: Props) {
  const locale = useLocale();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const otherLocale = locale === "zh" ? "en" : "zh";
  const label = locale === "zh" ? "EN" : "中";
  const fullLabel = locale === "zh" ? "English" : "中文";

  const handleSwitch = async () => {
    if (!user) return;
    try {
      await api.patch("/api/v1/auth/me/language", {
        language_preference: otherLocale === "zh" ? "zh-CN" : "en",
      });
    } catch {
      // 写 DB 失败不阻塞切换
    }
  };

  if (variant === "full") {
    return (
      <Link
        href={pathname}
        locale={otherLocale}
        onClick={handleSwitch}
        className="text-xs text-gray-400 transition-colors hover:text-gray-600"
      >
        {fullLabel}
      </Link>
    );
  }

  return (
    <Link
      href={pathname}
      locale={otherLocale}
      onClick={handleSwitch}
      className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-800"
      title={locale === "zh" ? "Switch to English" : "切换到中文"}
    >
      <Globe className="h-3.5 w-3.5" />
      {label}
    </Link>
  );
}
