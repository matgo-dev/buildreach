"use client";
import { ReactNode, useEffect } from "react";

import { TopStrip } from "./TopStrip";
import { MallHeader } from "./MallHeader";
import { MallNavRow } from "./MallNavRow";
import { MallFooter } from "./MallFooter";
import { FloatingWhatsApp } from "@/components/mall/FloatingWhatsApp";
import { useAuthStore } from "@/stores/authStore";
import { useCartStore } from "@/stores/cartStore";
import { getCart } from "@/lib/api/cart";

/**
 * 买方前台 Layout — 深青信任风格。
 *
 * 结构:TopStrip → MallHeader → MallNavRow → 内容 → MallFooter
 * 三栏布局由各页面自行组织(mall 页 = 左品类 + 中内容 + 右客服/RFQ)。
 */
export function PublicLayout({
  children,
  noContainer = false,
}: {
  children: ReactNode;
  noContainer?: boolean;
}) {
  const user = useAuthStore((s) => s.user);
  const syncFromCart = useCartStore((s) => s.syncFromCart);

  // 登录用户进入商城页面时自动加载购物车计数
  useEffect(() => {
    if (!user) return;
    getCart().then(syncFromCart).catch(() => {});
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="flex min-h-screen flex-col bg-bg overflow-x-hidden">
      <TopStrip />
      <MallHeader />
      <MallNavRow />
      <main className="flex-1">
        {noContainer ? children : (
          <div className="mx-auto max-w-mall px-3 sm:px-6 py-4 sm:py-6">
            {children}
          </div>
        )}
      </main>
      <MallFooter />
      <FloatingWhatsApp />
    </div>
  );
}
