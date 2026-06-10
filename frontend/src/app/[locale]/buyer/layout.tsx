"use client";

import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { getCart } from "@/lib/api/cart";

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const syncFromCart = useCartStore((s) => s.syncFromCart);

  // 登录后初始化询价篮角标
  useEffect(() => {
    if (!user) return;
    getCart().then(syncFromCart).catch(() => {});
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AppShell>
      <RouteGuard allowRoles={["BUYER"]}>
        {children}
      </RouteGuard>
    </AppShell>
  );
}
