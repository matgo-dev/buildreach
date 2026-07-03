"use client";
import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { useAuthStore } from "@/stores/authStore";
import type { RoleCode } from "@/lib/auth";
import type { PermissionCode } from "@/config/permission-matrix";

interface Props {
  /** 允许的角色(任一即可)。不传则只要登录即可。 */
  allowRoles?: RoleCode[];
  /** 要求拥有的权限点(全部都要)。 */
  requiredPermissions?: PermissionCode[];
  /** 要求持有该专区(Zone)的访问权限(code ∈ me.zones)。UX 层防护,后端 require_zone_access 才是安全底线。 */
  requireZone?: string;
  /** must_change_password=true 时是否强制跳改密。默认 true。 */
  enforceChangePassword?: boolean;
  children: ReactNode;
}

/**
 * 路由守卫(v3 §11)。顺序:loaded → 未登录 → 强制改密 → 角色限制 → 权限点限制 → 专区限制 → 通过
 *
 * UX 层防护,后端 require_permission / require_zone_access 才是安全底线。
 */
export function RouteGuard({
  allowRoles,
  requiredPermissions,
  requireZone,
  enforceChangePassword = true,
  children,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loaded } = useAuthStore();

  const missingPerm =
    user && requiredPermissions && requiredPermissions.length > 0
      ? requiredPermissions.find((p) => !user.permissions.includes(p))
      : undefined;

  const missingZone =
    !!user && !!requireZone && !user.zones.some((z) => z.code === requireZone);

  useEffect(() => {
    if (!loaded) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (enforceChangePassword && user.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
      return;
    }
    if (allowRoles && !allowRoles.some((r) => user.roles.includes(r))) {
      router.replace(`/no-permission?reason=role&route=${encodeURIComponent(pathname)}`);
      return;
    }
    if (missingPerm) {
      router.replace(
        `/no-permission?required=${encodeURIComponent(missingPerm)}&route=${encodeURIComponent(pathname)}`
      );
      return;
    }
    if (missingZone) {
      router.replace(`/no-permission?reason=zone&route=${encodeURIComponent(pathname)}`);
    }
  }, [user, loaded, allowRoles, missingPerm, missingZone, enforceChangePassword, pathname, router]);

  if (!loaded) return null;
  if (!user) return null;
  if (enforceChangePassword && user.must_change_password && pathname !== "/change-password") return null;
  if (allowRoles && !allowRoles.some((r) => user.roles.includes(r))) return null;
  if (missingPerm) return null;
  if (missingZone) return null;

  return <>{children}</>;
}
