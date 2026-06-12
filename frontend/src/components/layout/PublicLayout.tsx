"use client";
import { ReactNode, useEffect } from "react";
import { usePathname } from "@/i18n/navigation";

import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { useSidebarStore } from "@/stores/uiStore";

/** 公开区 Layout(顶部 nav,Logo 点击展开/收起左侧导航栏,内容区自适应)。 */
export function PublicLayout({
  children,
  noContainer = false,
}: {
  children: ReactNode;
  noContainer?: boolean;
}) {
  const open = useSidebarStore((s) => s.open);
  const close = useSidebarStore((s) => s.close);
  const pathname = usePathname();

  // 路由切换时自动收起
  useEffect(() => {
    close();
  }, [pathname, close]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <AppHeader showSearch showCart />
      <div className="flex flex-1 overflow-hidden">
        {open && (
          <div className="shrink-0">
            <AppSidebar />
          </div>
        )}
        <main className="flex-1 overflow-y-auto">
          {noContainer ? children : <div className="px-6 py-8">{children}</div>}
        </main>
      </div>
    </div>
  );
}
