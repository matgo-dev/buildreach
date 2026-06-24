"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, LogOut, Settings, ShieldCheck, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import { useLogout } from "@/hooks/useAuth";

/** 顶部深青公告条 — 公告 + 帮助 + 账号小入口 */
export function TopStrip() {
  const t = useTranslations("mall");
  const user = useAuthStore((s) => s.user);

  return (
    <div className="bg-teal-950 text-[#cfe6e6] text-[13px]">
      <div className="mx-auto max-w-mall px-6 flex items-center justify-between min-h-[36px]">
        <span className="hidden md:inline">
          {t("stripAnnouncement")}
        </span>
        <div className="flex items-center gap-4 text-xs whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-whatsapp/20 px-3 py-0.5 text-[#9af0bc] font-extrabold">
            <ShieldCheck className="h-3.5 w-3.5" />
            PVoC / CoC Document Support
          </span>
          <Link href="/help-center" className="hidden sm:inline hover:text-white transition-colors">{t("helpCenter")}</Link>
          <span className="text-teal-700">|</span>
          {user ? (
            <UserDropdown />
          ) : (
            <span className="inline-flex items-center gap-2">
              <Link href="/login" className="hover:text-white transition-colors">
                {t("headerLogin")}
              </Link>
              <span className="text-teal-700">|</span>
              <Link href="/register" className="hover:text-white transition-colors">
                {t("headerRegister")}
              </Link>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/** 用户下拉菜单 — 点击用户名展开，含个人资料 + 退出 */
function UserDropdown() {
  const t = useTranslations("mall");
  const user = useAuthStore((s) => s.user)!;
  const logout = useLogout();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 路由切换时关闭
  useEffect(() => { setOpen(false); }, [pathname]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 hover:text-white transition-colors"
      >
        <User className="h-3.5 w-3.5" />
        <span>{user.username || user.email}</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-[200] mt-1.5 w-40 rounded-lg border border-line bg-white py-1 shadow-lg">
          <Link
            href="/account"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-teal-50 hover:text-teal-900 transition-colors"
          >
            <Settings className="h-3.5 w-3.5 text-slate-400" />
            {t("stripProfile")}
          </Link>
          <div className="border-t border-slate-100 my-0.5" />
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            {t("menuLogout")}
          </button>
        </div>
      )}
    </div>
  );
}
