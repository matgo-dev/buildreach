"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { RbacTestPanel } from "../RbacTestPanel";

export default function BuyerOnlyPage() {
  return (
    <RouteGuard allowRoles={["BUYER"]}>
      <RbacTestPanel pageRole="BUYER" />
    </RouteGuard>
  );
}
