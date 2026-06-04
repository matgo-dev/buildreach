"use client";
import { useAuthStore } from "@/stores/authStore";
import type { RoleCode } from "@/lib/auth";

export function usePermissions() {
  const user = useAuthStore((s) => s.user);
  return {
    user,
    permissions: user?.permissions ?? [],
    roles: user?.roles ?? [],
    hasPermission: (code: string) => !!user && user.permissions.includes(code),
    hasRole: (code: RoleCode) => !!user && user.roles.includes(code),
    hasAnyRole: (codes: RoleCode[]) => !!user && codes.some((c) => user.roles.includes(c)),
  };
}
