"use client";
import { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { PublicNav } from "./PublicNav";
import { RouteGuard } from "@/components/auth/RouteGuard";

/**
 * 工作台 Layout(用于 buyer / supplier / operator / admin 路由)。
 * 内部包了 RouteGuard:必须登录,且 must_change_password=true 时强制改密。
 * 精细的权限点校验由各 page 的 PermissionPlaceholderPage 内部处理。
 *
 * 顶部 header 中央插槽放公开区主导航,与公开 layout 保持一致;
 * 侧边栏只渲染当前工作台的 tab,不再重复公开区入口。
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <RouteGuard>
      <div className="flex min-h-screen flex-col bg-slate-50">
        <AppHeader centerNav={<PublicNav />} />
        <div className="flex flex-1">
          <AppSidebar />
          <main className="flex-1 overflow-x-auto">
            <div className="p-6">{children}</div>
          </main>
        </div>
      </div>
    </RouteGuard>
  );
}
