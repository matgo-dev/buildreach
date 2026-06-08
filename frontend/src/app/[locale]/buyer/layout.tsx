"use client";

import { AppShell } from "@/components/layout/AppShell";
import { RouteGuard } from "@/components/auth/RouteGuard";

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <RouteGuard allowRoles={["BUYER"]}>
        {children}
      </RouteGuard>
    </AppShell>
  );
}
