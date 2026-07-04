// 运营端 — 专区授权(zone_grants)管理 API
//
// 后端契约见 backend/app/api/v1/operator_zones.py
import { api } from "../api";

export interface ZoneBrief {
  id: number;
  code: string;
  name_zh: string;
  status: string;
}

export interface ZoneGrantOut {
  buyer_org_id: number;
  name: string;
  code: string | null;
  granted_at: string | null;
}

export const zoneGrantsApi = {
  listZones: () => api.get<ZoneBrief[]>("/api/v1/operator/zones"),
  listGrants: (zoneCode: string) =>
    api.get<ZoneGrantOut[]>(
      `/api/v1/operator/zones/${encodeURIComponent(zoneCode)}/grants`,
    ),
  grant: (zoneCode: string, buyerOrgId: number) =>
    api.post<ZoneGrantOut>(
      `/api/v1/operator/zones/${encodeURIComponent(zoneCode)}/grants`,
      { buyer_org_id: buyerOrgId },
    ),
  revoke: (zoneCode: string, buyerOrgId: number) =>
    api.delete(
      `/api/v1/operator/zones/${encodeURIComponent(zoneCode)}/grants/${buyerOrgId}`,
    ),
};
