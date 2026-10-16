"use client";

import useSWR from "swr";

import { zonesApi } from "@/lib/api/zones";
import type { ZoneBriefForUser } from "@/lib/zoneName";
import { useAuthStore } from "@/stores/authStore";

/**
 * 当前访问者可进的专区(导航入口、专区页门禁、专区名共用)。
 * 已登录用 /me 的 zones(公开专区 + 已授权专区),未登录拉 GET /zones(只含公开专区);两者后端同一口径。
 */
export function useAccessibleZones(): { zones: ZoneBriefForUser[]; loaded: boolean } {
  const user = useAuthStore((s) => s.user);
  const authLoaded = useAuthStore((s) => s.loaded);
  const anonymous = authLoaded && !user;
  const { data, error } = useSWR(anonymous ? "zones:accessible:anonymous" : null, () => zonesApi.list());

  if (!authLoaded) return { zones: [], loaded: false };
  if (user) return { zones: user.zones, loaded: true };
  return { zones: data ?? [], loaded: data !== undefined || error !== undefined };
}
