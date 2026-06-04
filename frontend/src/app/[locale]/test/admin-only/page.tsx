"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { RbacTestPanel } from "../RbacTestPanel";

export default function AdminOnlyPage() {
  return (
    <RouteGuard allowRoles={["ADMIN"]}>
      <RbacTestPanel pageRole="ADMIN" />
    </RouteGuard>
  );
}
