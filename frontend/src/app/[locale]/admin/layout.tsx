"use client";

import { AppShell } from "@/components/layout/AppShell";
import { RouteGuard } from "@/components/auth/RouteGuard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <RouteGuard allowRoles={["ADMIN"]}>
        {children}
      </RouteGuard>
    </AppShell>
  );
}
