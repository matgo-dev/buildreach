"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { RbacTestPanel } from "../RbacTestPanel";

export default function SupplierOnlyPage() {
  return (
    <RouteGuard allowRoles={["SUPPLIER"]}>
      <RbacTestPanel pageRole="SUPPLIER" />
    </RouteGuard>
  );
}
