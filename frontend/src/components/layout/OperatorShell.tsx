"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, usePathname } from "@/i18n/navigation";
import { Search, Bell, MessageSquare, ChevronDown, Phone, LogOut, LayoutDashboard } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { useAuthStore } from "@/stores/authStore";
import { useLogout } from "@/hooks/useAuth";
import { WORKSPACES, type NavItem } from "@/config/navigation";
import { scopeOf } from "@/config/permission-matrix";
import type { RoleCode } from "@/lib/auth";

/**
 * 运营后台专属布局 — 对标东非 Demo 截图后台风格。
 * 深 teal 侧边栏 + 浅灰背景 + 紧凑顶栏。
 */
export function OperatorShell({ children }: { children: ReactNode }) {
  return (
    <RouteGuard>
      <div className="flex min-h-screen bg-[#F1F5F9]">
        <OperatorSidebar />
        <div className="flex flex-1 flex-col min-w-0">
          <OperatorTopbar />
          <main className="flex-1 overflow-x-auto p-5">{children}</main>
        </div>
      </div>
    </RouteGuard>
  );
}

function OperatorTopbar() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // 点外部关闭
  useEffect(() => {
    if (!userMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (!userMenuRef.current?.contains(e.target as Node)) setUserMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [userMenuOpen]);

  const displayName = user?.username || user?.email || "Admin";
  const initial = (displayName[0] ?? "O").toUpperCase();

  return (
    <header className="flex h-[50px] items-center justify-between border-b border-slate-200 bg-white px-5">
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="搜索商品、供应商、订单... / Search products, supplier, compliance..."
          className="w-full rounded-md border border-slate-200 bg-[#F8FAFC] py-1.5 pl-10 pr-4 text-[12px] text-slate-700 placeholder:text-slate-400 focus:border-[#0D4D4D] focus:outline-none"
        />
      </div>
      <div className="flex items-center gap-4">
        <button className="relative rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[8px] text-white">3</span>
        </button>
        <button className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100">
          <MessageSquare className="h-4 w-4" />
        </button>

        {/* 用户下拉菜单 */}
        <div ref={userMenuRef} className="relative">
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-lg px-2 py-1 text-[12px] hover:bg-slate-50 transition-colors"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0D4D4D] text-[11px] font-bold text-white">
              {initial}
            </div>
            <span className="text-slate-700 font-medium">{displayName}</span>
            <ChevronDown className={`h-3 w-3 text-slate-400 transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full z-50 mt-1.5 w-48 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
              <div className="border-b border-slate-100 px-3 py-2.5">
                <p className="text-[12px] font-medium text-slate-800">{displayName}</p>
                {user?.email && user.email !== displayName && (
                  <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
                )}
              </div>
              <div className="py-1">
                <Link
                  href="/"
                  className="flex items-center gap-2 px-3 py-2 text-[12px] text-slate-600 hover:bg-slate-50"
                  onClick={() => setUserMenuOpen(false)}
                >
                  <LayoutDashboard className="h-3.5 w-3.5 text-slate-400" />
                  返回首页
                </Link>
              </div>
              <div className="border-t border-slate-100 py-1">
                <button
                  onClick={() => { setUserMenuOpen(false); logout(); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-[12px] text-red-500 hover:bg-red-50"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  退出登录
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function OperatorSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  if (!user) return null;

  const userPerms = new Set(user.permissions);
  const userRoles = user.roles as RoleCode[];

  // 拿 OPERATOR workspace 的菜单
  const operatorWs = WORKSPACES.find((w) => w.code === "OPERATOR");
  const items = operatorWs?.groups.flatMap((g) => g.items) ?? [];

  const checkAccess = (item: NavItem) => {
    if (item.resource) {
      const scope = scopeOf(userRoles, item.resource);
      if (scope === "NONE") return false;
    }
    if (item.requiredPermissions.length > 0) {
      return item.requiredPermissions.every((p) => userPerms.has(p));
    }
    return true;
  };

  return (
    <aside className="flex w-[220px] shrink-0 flex-col bg-[#0D3D3D]">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-white/10 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10 text-[14px] font-bold text-white">EA</div>
        <div className="leading-tight">
          <p className="text-[13px] font-bold text-white">East Africa</p>
          <p className="text-[9px] text-white/50">Building Materials Hub Admin</p>
        </div>
      </div>

      {/* 菜单 */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {items.filter(checkAccess).map((item) => {
          const isActive = pathname === item.path || pathname.startsWith(item.path + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              href={item.path}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-colors ${
                isActive
                  ? "bg-[#0D5D5D] text-white"
                  : "text-white/60 hover:bg-white/5 hover:text-white/90"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <div className="min-w-0 leading-tight">
                <span className="block truncate">{item.label}</span>
                {item.labelEn && (
                  <span className={`block text-[9px] ${isActive ? "text-white/50" : "text-white/30"}`}>
                    {item.labelEn}
                  </span>
                )}
              </div>
            </Link>
          );
        })}
      </nav>

      {/* 底部联系 */}
      <div className="border-t border-white/10 px-4 py-3">
        <div className="flex items-center gap-2 text-[11px] text-white/50">
          <Phone className="h-3 w-3" />
          <span>+255 697 123 456</span>
        </div>
        <p className="mt-0.5 text-[10px] text-white/30">Support: Mon-Sat 8:00-18:00</p>
      </div>
    </aside>
  );
}
