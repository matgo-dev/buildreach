"use client";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import ProductDetailPage from "./_components/ProductDetailPage";

export default function OperatorProductDetailRoute() {
  return (
    <RouteGuard requiredPermissions={[Permissions.PRODUCT_READ]}>
      <ProductDetailPage />
    </RouteGuard>
  );
}
