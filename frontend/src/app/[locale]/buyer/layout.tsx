"use client";

import { useEffect } from "react";
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
 * Buyer 工作台 Layout — 顶部沿用 Mall 深青 Header,左侧保留工作台侧边栏。
 *
 * 结构:TopStrip → MallHeader → MallNavRow → (Sidebar + Content) → MallFooter
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
        <div className="flex flex-1 overflow-hidden">
          <AppSidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="p-6">{children}</div>
          </main>
        </div>
        <MallFooter />
      </div>
    </RouteGuard>
  );
}
