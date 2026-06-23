"use client";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { OrderTrackingPage } from "@/components/order-tracking/OrderTrackingPage";

export default function OrderTrackingRoute() {
  return (
    <PublicLayout>
      <OrderTrackingPage />
    </PublicLayout>
  );
}
