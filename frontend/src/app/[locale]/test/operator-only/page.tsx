"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { RbacTestPanel } from "../RbacTestPanel";

export default function OperatorOnlyPage() {
  return (
    <RouteGuard allowRoles={["OPERATOR"]}>
      <RbacTestPanel pageRole="OPERATOR" />
    </RouteGuard>
  );
}
