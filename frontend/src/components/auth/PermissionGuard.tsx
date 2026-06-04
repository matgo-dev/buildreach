"use client";
import { ReactNode } from "react";
import { usePermissions } from "@/hooks/usePermissions";
import type { RoleCode } from "@/lib/auth";

interface Props {
  required?: string;
  anyOf?: string[];
  role?: RoleCode;
  anyRole?: RoleCode[];
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * 按钮/区块的显隐守卫(前端友好交互层,非安全底线 — 后端 require_permission 才是)。
 */
export function PermissionGuard({
  required,
  anyOf,
  role,
  anyRole,
  children,
  fallback = null,
}: Props) {
  const { hasPermission, hasRole, hasAnyRole } = usePermissions();
  let ok = true;
  if (required) ok = ok && hasPermission(required);
  if (anyOf && anyOf.length > 0) ok = ok && anyOf.some(hasPermission);
  if (role) ok = ok && hasRole(role);
  if (anyRole && anyRole.length > 0) ok = ok && hasAnyRole(anyRole);
  return <>{ok ? children : fallback}</>;
}
