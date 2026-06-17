"use client";

import { useEffect } from "react";
import { TopStrip } from "@/components/layout/TopStrip";
import { MallHeader } from "@/components/layout/MallHeader";
import { MallNavRow } from "@/components/layout/MallNavRow";
import { MallFooter } from "@/components/layout/MallFooter";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { getCart } from "@/lib/api/cart";

/**
 * Buyer Layout — 与商城体验统一，使用 PublicLayout 风格（顶部导航 + 全宽内容）。
 * 不使用侧边栏工作台，买方所有页面保持在商城导航体系内。
 */
export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const syncFromCart = useCartStore((s) => s.syncFromCart);

  useEffect(() => {
    if (!user) return;
    getCart().then(syncFromCart).catch(() => {});
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

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
