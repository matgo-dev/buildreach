"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ChevronDown,
  LayoutDashboard,
  LogOut,
  MapPin,
  Search,
  Settings,
  ShoppingCart,
  User,
} from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { useLogout } from "@/hooks/useAuth";
import { BRAND } from "@/config/brand";
import { workspaceDashboardOf } from "@/config/navigation";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import type { RoleCode } from "@/lib/auth";

/** 角色标签 labelKey 对应 mall.roleBuyer 等 */
const ROLE_PILL: Record<RoleCode, { labelKey: string; cls: string }> = {
  BUYER:    { labelKey: "roleBuyer",    cls: "bg-teal-100 text-teal-900 border-teal-800/20" },
  SUPPLIER: { labelKey: "roleSupplier", cls: "bg-gold-soft text-gold-deep border-gold/30" },
  OPERATOR: { labelKey: "roleOperator", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  ADMIN:    { labelKey: "roleAdmin",    cls: "bg-slate-100 text-slate-700 border-slate-200" },
};

/** Mall 专属 Header — 深青底色 + 大搜索框 + 暖金点缀。参考 HTML .mainbar */
export function MallHeader() {
  const user = useAuthStore((s) => s.user);
  const cartCount = useCartStore((s) => s.count);
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const [searchValue, setSearchValue] = useState("");

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
    <header
      className="sticky top-0 z-[60] border-b-2 border-gold"
      style={{
        background: "linear-gradient(180deg, #00505a, #003f46)",
        boxShadow: "0 12px 30px rgba(0,63,70,.22)",
      }}
    >
      <div className="mx-auto max-w-mall px-6 grid grid-cols-[320px_minmax(360px,1fr)_auto] items-center gap-6 min-h-[80px]">
        {/* 左:品牌 */}
        <Link
          href="/"
          className="flex items-center gap-3.5 group"
          aria-label={BRAND.name}
        >
          {/* Logo 建筑图标 — 暖金渐变底 */}
          <span
            className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-white font-black text-lg"
            style={{
              background: "linear-gradient(135deg, #e3a615, #a36900)",
              boxShadow: "0 4px 12px rgba(216,139,0,0.3)",
            }}
          >
            {BRAND.logoChar}
          </span>
          <span className="min-w-0">
            <strong className="block text-[17px] leading-tight font-black text-white">
              {t("brandName")}
            </strong>
            <span className="block mt-1 text-[13px] text-[#bfe1e0] truncate">
              {t("brandNameSub")}
            </span>
          </span>
        </Link>

        {/* 中:搜索框 — 暖金边框 */}
        <form onSubmit={handleSearch} className="min-w-0">
          <div
            className="flex rounded-[10px] overflow-hidden"
            style={{
              border: "2px solid #e3a615",
              boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
            }}
          >
            <input
              type="search"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="flex-1 h-12 px-4 bg-white text-ink text-[14.5px] outline-none min-w-0"
            />
            <button
              type="submit"
              className="w-[60px] bg-gold hover:bg-gold-deep text-white grid place-items-center transition-colors"
              aria-label="Search"
            >
              <Search className="h-5 w-5" strokeWidth={2.4} />
            </button>
          </div>
        </form>

        {/* 右:操作区 */}
        <div className="flex items-center gap-1.5">
          {/* 收货地 — 纯展示 */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-2 text-white/70">
            <MapPin className="h-4 w-4 shrink-0" />
            <span className="text-xs">
              <strong className="block text-[13px] leading-tight font-bold text-white/90">{BRAND.deliverTo}</strong>
              {t("headerDeliverTo")}
            </span>
          </div>

          {/* 询价车 */}
          <Link
            href={user ? "/buyer/cart" : "/login"}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-white hover:bg-white/[0.08] transition-colors"
          >
            <div className="relative">
              <ShoppingCart className="h-5 w-5" />
              <span
                className="absolute -right-2.5 -top-2 flex h-[19px] min-w-[19px] items-center justify-center rounded-full text-[11px] font-black text-white border-2 border-teal-900"
                style={{ background: "#e3a615" }}
              >
                {cartCount}
              </span>
            </div>
            <span className="text-xs hidden lg:block">
              <strong className="block text-[13.5px] leading-tight font-black">{t("headerQuoteByCS")}</strong>
              {t("headerRfqCart")}
            </span>
          </Link>

          {/* 用户 */}
          {user ? (
            <UserMenu />
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-white hover:bg-white/[0.08] transition-colors"
            >
              <User className="h-5 w-5" />
              <span className="text-xs hidden lg:block">
                <strong className="block text-[13.5px] leading-tight font-black">{t("headerMyAccount")}</strong>
                {t("headerAccountSub")}
              </span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

/** 用户下拉菜单 */
function UserMenu() {
  const user = useAuthStore((s) => s.user)!;
  const logout = useLogout();
  const pathname = usePathname();
  const t = useTranslations("mall");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { setOpen(false); }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [open]);

  const displayName = user.username || user.email;
  const initial = (displayName?.[0] ?? "U").toUpperCase();
  const dashboardHref = workspaceDashboardOf(user.roles);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-white hover:bg-white/[0.08] transition-colors"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <User className="h-5 w-5" />
        <span className="text-xs hidden lg:block">
          <strong className="block text-[13.5px] leading-tight font-black max-w-[100px] truncate">
            {displayName}
          </strong>
          {t("headerMyAccount")}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full z-[9999] mt-2 w-60 overflow-hidden rounded-xl border border-line bg-white shadow-mall-lg">
          {/* 用户信息 */}
          <div className="border-b border-slate-100 bg-gradient-to-br from-teal-50 to-white px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
                style={{ background: "linear-gradient(135deg, #07808b, #00505a)" }}>
                {initial}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-navy">{displayName}</p>
                {user.email && user.email !== displayName && (
                  <p className="truncate text-xs text-muted">{user.email}</p>
                )}
              </div>
            </div>
            {user.roles.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {user.roles.map((r) => {
                  const meta = ROLE_PILL[r];
                  return (
                    <span key={r} className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${meta?.cls ?? "border-slate-200 bg-slate-50 text-slate-600"}`}>
                      {meta ? t(meta.labelKey) : r}
                    </span>
                  );
                })}
              </div>
            )}
          </div>

          <div className="py-1.5">
            <Link
              href={dashboardHref}
              role="menuitem"
              className="flex items-center gap-2.5 px-4 py-2 text-sm text-slate-700 hover:bg-teal-50 hover:text-teal-900 transition-colors"
            >
              <LayoutDashboard className="h-4 w-4 text-muted" />
              {t("menuDashboard")}
            </Link>
            <span
              role="menuitem"
              aria-disabled
              title={t("menuSettingsDisabled")}
              className="flex cursor-not-allowed select-none items-center gap-2.5 px-4 py-2 text-sm text-slate-400"
            >
              <Settings className="h-4 w-4 text-slate-300" />
              {t("menuSettings")}
              <span className="ml-auto text-[10px] text-slate-300">{t("menuSettingsDisabled")}</span>
            </span>
          </div>

          <div className="border-t border-slate-100 py-1.5">
            <button
              onClick={() => { setOpen(false); logout(); }}
              role="menuitem"
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              {t("menuLogout")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
