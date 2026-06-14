"use client";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  Bug,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Search,
  Settings,
  ShoppingCart,
  Sparkles,
} from "lucide-react";

import { useLocale, useTranslations } from "next-intl";
import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { useDebugMode } from "@/stores/uiStore";
import { useLogout } from "@/hooks/useAuth";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { BRAND } from "@/config/brand";
import { defaultDashboardOf, workspaceDashboardOf } from "@/config/navigation";
import { useSidebarStore } from "@/stores/uiStore";
import type { RoleCode } from "@/lib/auth";

const ROLE_PILL: Record<RoleCode, { label: string; cls: string }> = {
  BUYER:    { label: "采购方",     cls: "bg-blue-50 text-blue-700 border-blue-200" },
  SUPPLIER: { label: "供应商",     cls: "bg-orange-50 text-orange-700 border-orange-200" },
  OPERATOR: { label: "平台运营",   cls: "bg-sky-50 text-sky-700 border-sky-200" },
  ADMIN:    { label: "系统管理员", cls: "bg-slate-100 text-slate-700 border-slate-200" },
};

/** 顶部 Header(工作台 + 公开区共用)。 */
export function AppHeader({
  showDebugToggle = false,
  centerNav,
  showSearch = false,
  showCart = false,
}: {
  showDebugToggle?: boolean;
  /** 中间区域插槽,公开区在此渲染主导航 */
  centerNav?: ReactNode;
  /** 显示搜索框占位 */
  showSearch?: boolean;
  /** 显示询价篮图标 */
  showCart?: boolean;
}) {
  const user = useAuthStore((s) => s.user);
  const cartCount = useCartStore((s) => s.count);
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const [searchValue, setSearchValue] = useState("");
  const [debugMode, setDebugMode] = useDebugMode();
  const toggleSidebar = useSidebarStore((s) => s.toggle);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const kw = searchValue.trim();
      const qs = kw ? `?keyword=${encodeURIComponent(kw)}` : "";
      router.push(`/${locale}/mall${qs}`);
    },
    [searchValue, router, locale],
  );

  return (
    <header className="shrink-0 z-50 border-b border-slate-200 bg-white">
      <div className="flex h-16 items-center justify-between gap-4 px-6">
        {/* 左:品牌 — 已登录切换侧边栏,未登录跳首页 */}
        {user ? (
          <button onClick={toggleSidebar} className="group flex shrink-0 items-center gap-3 cursor-pointer" aria-label={`${BRAND.name} 菜单`}>
            <span className="relative flex h-8 w-8 items-center justify-center rounded bg-teal-900 transition-transform duration-300 group-hover:scale-105">
              <span className="select-none text-sm font-black leading-none text-white">{BRAND.logoChar}</span>
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-gold" />
            </span>
            <span className="leading-none text-left">
              <span className="block text-xl font-black tracking-tight text-teal-900">{BRAND.name}</span>
              <span className="mt-0.5 block text-[9px] font-medium tracking-[0.15em] text-gray-400">{BRAND.nameEn}</span>
            </span>
          </button>
        ) : (
          <Link href="/" className="group flex shrink-0 items-center gap-3" aria-label={`${BRAND.name} 首页`}>
            <span className="relative flex h-8 w-8 items-center justify-center rounded bg-teal-900 transition-transform duration-300 group-hover:scale-105">
              <span className="select-none text-sm font-black leading-none text-white">{BRAND.logoChar}</span>
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-gold" />
            </span>
            <span className="leading-none">
              <span className="block text-xl font-black tracking-tight text-teal-900">{BRAND.name}</span>
              <span className="mt-0.5 block text-[9px] font-medium tracking-[0.15em] text-gray-400">{BRAND.nameEn}</span>
            </span>
          </Link>
        )}

        {/* 中:搜索框占位 或 导航插槽 */}
        {showSearch ? (
          <form onSubmit={handleSearch} className="flex flex-1 max-w-xl">
            <div className="relative w-full">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                placeholder={t("searchPlaceholder")}
                className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-12 text-sm text-gray-700 placeholder-gray-400 transition-colors hover:border-slate-300 focus:border-teal-900 focus:outline-none focus:ring-1 focus:ring-teal-900/20"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 flex h-7 items-center rounded-md bg-teal-900 px-2.5 text-xs font-medium text-white transition-colors hover:bg-teal-950"
              >
                <Search className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>
        ) : (
          centerNav && <div className="flex flex-1 justify-center">{centerNav}</div>
        )}

        {/* 右:询价篮 + 调试 toggle + 语言 + 用户 */}
        <div className="flex items-center gap-3">
          {showCart && (
            <Link
              href={user ? "/buyer/cart" : "/login"}
              className="relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-teal-900"
              title="询价篮"
            >
              <ShoppingCart className="h-5 w-5" />
              {user && cartCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-gold px-1 text-[10px] font-bold text-white">
                  {cartCount > 99 ? "99+" : cartCount}
                </span>
              )}
            </Link>
          )}

          {showDebugToggle && (
            <button
              onClick={() => setDebugMode(!debugMode)}
              title={debugMode ? "调试模式:显示所有 tab(无权置灰)" : "线上模式:仅显示有权 tab"}
              className={
                "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors " +
                (debugMode
                  ? "border-gold/40 bg-gold/10 text-gold"
                  : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50")
              }
            >
              {debugMode ? <Bug className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
              {debugMode ? "调试模式" : "线上模式"}
            </button>
          )}

          <LocaleSwitcher />

          {user ? (
            <UserMenu />
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-teal-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-950"
            >
              登录
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

/** 用户下拉菜单:头像 + 名字 + chevron 触发,展开后展示用户信息卡 + 入口 + 退出。 */
function UserMenu() {
  const user = useAuthStore((s) => s.user)!;
  const logout = useLogout();
  const pathname = usePathname();

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 路由变化自动关闭
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // 点外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const displayName = user.username || user.email;
  const initial = (displayName?.[0] ?? "U").toUpperCase();
  const primaryRole = user.roles[0];
  const dashboardHref = workspaceDashboardOf(user.roles);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className={
          "flex items-center gap-2 rounded-full border py-1 pl-1 pr-3 transition-colors " +
          (open
            ? "border-teal-900/30 bg-slate-50"
            : "border-slate-200 hover:border-teal-900/30 hover:bg-slate-50")
        }
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-teal-900 to-teal-800 text-xs font-bold text-white shadow-sm">
          {initial}
        </span>
        <span className="max-w-[120px] truncate text-sm font-medium text-slate-700">
          {displayName}
        </span>
        <ChevronDown
          className={
            "h-3.5 w-3.5 text-slate-400 transition-transform duration-200 " +
            (open ? "rotate-180" : "")
          }
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-[200] mt-2 w-60 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl"
        >
          {/* 用户信息卡 */}
          <div className="border-b border-slate-100 bg-gradient-to-br from-slate-50 to-white px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-teal-900 to-teal-800 text-sm font-bold text-white">
                {initial}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
                {user.email && user.email !== displayName && (
                  <p className="truncate text-xs text-slate-400">{user.email}</p>
                )}
              </div>
            </div>
            {user.roles.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {user.roles.map((r) => {
                  const meta = ROLE_PILL[r];
                  return (
                    <span
                      key={r}
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${meta?.cls ?? "border-slate-200 bg-slate-50 text-slate-600"}`}
                    >
                      {meta?.label ?? r}
                    </span>
                  );
                })}
              </div>
            )}
          </div>

          {/* 菜单项 */}
          <div className="py-1.5">
            {primaryRole && (
              <Link
                href={dashboardHref}
                role="menuitem"
                className="flex items-center gap-2.5 px-4 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50 hover:text-teal-900"
              >
                <LayoutDashboard className="h-4 w-4 text-slate-400" />
                工作台
              </Link>
            )}
            <span
              role="menuitem"
              aria-disabled
              title="账户设置改版中"
              className="flex cursor-not-allowed select-none items-center gap-2.5 px-4 py-2 text-sm text-slate-400"
            >
              <Settings className="h-4 w-4 text-slate-300" />
              账户设置
              <span className="ml-auto text-[10px] text-slate-300">改版中</span>
            </span>
          </div>

          {/* 退出 */}
          <div className="border-t border-slate-100 py-1.5">
            <button
              onClick={() => {
                setOpen(false);
                logout();
              }}
              role="menuitem"
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-500 transition-colors hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
