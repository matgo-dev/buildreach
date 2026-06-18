"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { TopStrip } from "@/components/layout/TopStrip";
import { MallHeader } from "@/components/layout/MallHeader";
import { MallNavRow } from "@/components/layout/MallNavRow";
import { MallFooter } from "@/components/layout/MallFooter";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { getCart } from "@/lib/api/cart";

/**
 * Buyer Layout — 两种模式：
 * 1. 商城体验页（询价篮 /buyer/cart）：无侧边栏，全宽内容，与商城页面一致
 * 2. 工作台页面（询价管理、订单管理等）：保留侧边栏
 */

// 使用商城布局（无侧边栏）的路径
const MALL_STYLE_PATHS = ["/buyer/cart", "/buyer/rfqs/create"];

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const pathname = usePathname();

  useEffect(() => {
    if (!user) return;
    getCart().then(syncFromCart).catch(() => {});
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // 去掉 locale 前缀判断实际路径
  const bare = pathname.replace(/^\/[a-z]{2}(?=\/)/, "");
  const isMallStyle = MALL_STYLE_PATHS.some((p) => bare === p || bare.startsWith(p + "/"));

  if (isMallStyle) {
    // 商城风格：无侧边栏，有顶部导航
    return (
      <RouteGuard allowRoles={["BUYER"]}>
        <div className="flex min-h-screen flex-col bg-bg">
          <TopStrip />
          <MallHeader />
          <MallNavRow />
          <main className="flex-1">
            <div className="mx-auto max-w-mall px-6 py-6">{children}</div>
          </main>
          <MallFooter />
        </div>
      </RouteGuard>
    );
  }

  // 工作台风格：有侧边栏
  return (
    <RouteGuard allowRoles={["BUYER"]}>
      <div className="flex h-screen flex-col overflow-hidden bg-bg">
        <TopStrip />
        <MallHeader />
        <div className="flex flex-1 overflow-hidden">
          <AppSidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="p-6">{children}</div>
          </main>
        </div>
      </div>
    </RouteGuard>
  );
}
