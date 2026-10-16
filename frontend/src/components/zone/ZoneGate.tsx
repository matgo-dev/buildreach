"use client";

import { ReactNode, useEffect } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { useAccessibleZones } from "@/hooks/useAccessibleZones";
import { useAuthStore } from "@/stores/authStore";

/**
 * 专区页门禁(UX 层,后端 require_zone_access 才是安全底线)。
 * 公开专区所有人(含未登录)直接进;非公开专区未登录去登录,已登录无授权去无权限页。
 */
export function ZoneGate({ zoneCode, children }: { zoneCode: string; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const { zones, loaded } = useAccessibleZones();
  const allowed = zones.some((z) => z.code === zoneCode);

  useEffect(() => {
    if (!loaded || allowed) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else router.replace(`/no-permission?reason=zone&route=${encodeURIComponent(pathname)}`);
  }, [loaded, allowed, user, pathname, router]);

  if (!loaded || !allowed) return null;
  return <>{children}</>;
}
