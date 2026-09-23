"use client";

import { useAuthStore } from "@/stores/authStore";
import { BuyerOrders } from "./BuyerOrders";
import { MOCK_ORDERS_SOURCE } from "./mockOrders";

/** 订单追踪页 — demo 账号看 mock 数据(营销用途),真实用户接履约后台(经 BFF);两者同一套渲染。 */
export function OrderTrackingPage() {
  const user = useAuthStore((s) => s.user);
  const isDemo = user?.is_demo ?? false;
  return <BuyerOrders source={isDemo ? MOCK_ORDERS_SOURCE : undefined} />;
}
