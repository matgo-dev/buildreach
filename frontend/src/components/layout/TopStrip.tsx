"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, LayoutDashboard, LogOut, Settings, ShieldCheck, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import { useLogout } from "@/hooks/useAuth";
import { workspaceDashboardOf } from "@/config/navigation";

/** 顶部深青公告条 — 公告 + 帮助 + 账号小入口 */
export function TopStrip() {
  const t = useTranslations("mall");
  const user = useAuthStore((s) => s.user);

  return (
    <div className="bg-teal-700 text-white/85 text-[13px]">
      <div className="mx-auto max-w-mall px-3 sm:px-6 flex items-center justify-between min-h-[32px] sm:min-h-[36px]">
        <span className="hidden md:inline">
          {t("stripAnnouncement")}
        </span>
        <div className="flex items-center gap-2 sm:gap-4 text-xs whitespace-nowrap overflow-visible">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-whatsapp/20 px-2 sm:px-3 py-0.5 text-[#9af0bc] font-extrabold text-[11px] sm:text-xs shrink-0">
            <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
            <span className="hidden sm:inline">PVoC / CoC Document Support</span>
            <span className="sm:hidden">PVoC / CoC</span>
          </span>
          <Link href="/help-center" className="hidden sm:inline hover:text-white transition-colors">{t("helpCenter")}</Link>
          <span className="text-white/40">|</span>
          {user ? (
            <UserDropdown />
          ) : (
            <span className="inline-flex items-center gap-2 shrink-0">
              <Link href="/login" className="hover:text-white transition-colors">
                {t("headerLogin")}
              </Link>
              <span className="text-white/40">|</span>
              <Link href="/register" className="hover:text-white transition-colors truncate max-w-[120px] sm:max-w-none">
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

  // 内部员工(运营/管理员)在公开商城页也能一键回工作台
  const isStaff = user.roles?.some((r) => r === "OPERATOR" || r === "ADMIN");

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
          {isStaff && (
            <Link
              href={workspaceDashboardOf(user.roles)}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-teal-50 hover:text-teal-900 transition-colors"
            >
              <LayoutDashboard className="h-3.5 w-3.5 text-slate-400" />
              {t("menuDashboard")}
            </Link>
          )}
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
