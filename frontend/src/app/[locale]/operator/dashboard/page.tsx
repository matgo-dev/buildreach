"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function Page() {
  return (
    <RouteGuard>
      <PermissionPlaceholderPage />
    </RouteGuard>
  );
}
