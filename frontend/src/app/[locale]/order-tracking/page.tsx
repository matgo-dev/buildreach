"use client";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { OrderTrackingPage } from "@/components/order-tracking/OrderTrackingPage";

export default function OrderTrackingRoute() {
  return (
    <PublicLayout>
      <RouteGuard allowRoles={["BUYER"]}>
        <OrderTrackingPage />
      </RouteGuard>
    </PublicLayout>
  );
}
