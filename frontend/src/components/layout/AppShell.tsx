"use client";
import { ReactNode, useEffect } from "react";

import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useAuthStore } from "@/stores/authStore";
import { useSidebarStore } from "@/stores/uiStore";

/**
 * 工作台 Layout(用于 buyer / supplier / operator / admin 路由)。
 * 内部包了 RouteGuard:必须登录,且 must_change_password=true 时强制改密。
 *
 * Buyer 工作台:顶部显示搜索框 + 询价篮(与商城体验统一)。
 * 其他角色工作台:顶部纯净,不显示搜索框/询价篮。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const isBuyer = user?.roles.includes("BUYER") ?? false;

  // 工作台已有固定侧边栏，确保 overlay 状态关闭
  const close = useSidebarStore((s) => s.close);
  useEffect(() => { close(); }, [close]);

  return (
    <RouteGuard>
      <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
        <AppHeader showSearch={isBuyer} showCart={isBuyer} />
        <div className="flex flex-1 overflow-hidden">
          <AppSidebar />
          <main className="flex-1 overflow-y-auto overflow-x-auto">
            <div className="p-6">{children}</div>
          </main>
        </div>
      </div>
    </RouteGuard>
  );
}
