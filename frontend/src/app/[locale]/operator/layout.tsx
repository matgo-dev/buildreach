"use client";

import { AppShell } from "@/components/layout/AppShell";
import { RouteGuard } from "@/components/auth/RouteGuard";

export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <RouteGuard allowRoles={["OPERATOR"]}>
        {children}
      </RouteGuard>
    </AppShell>
  );
}
