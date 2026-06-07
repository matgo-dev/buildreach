"use client";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { ProductCreatePage } from "./_components/ProductCreatePage";

export default function Page() {
  return (
    <RouteGuard requiredPermissions={[Permissions.PRODUCT_WRITE]}>
      <ProductCreatePage />
    </RouteGuard>
  );
}
