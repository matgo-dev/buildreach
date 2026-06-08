"use client";

import { AppShell } from "@/components/layout/AppShell";
import { RouteGuard } from "@/components/auth/RouteGuard";

export default function SupplierLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <RouteGuard allowRoles={["SUPPLIER"]}>
        {children}
      </RouteGuard>
    </AppShell>
  );
}
