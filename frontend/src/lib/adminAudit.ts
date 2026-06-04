// /api/v1/admin/audit-logs 客户端

import { api } from "./api";

export interface AuditLogOut {
  id: number;
  trace_id: string;
  user_id: number | null;
  user_email: string | null;
  resource_type: string;
  resource_id: string | null;
  action: string;
  method: string | null;
  path: string | null;
  ip: string | null;
  user_agent: string | null;
  status: "SUCCESS" | "FAILED";
  error_message: string | null;
  extra: Record<string, unknown> | null;
  /** ISO 8601,naive UTC,无 Z 后缀,前端按需转 */
  created_at: string | null;
}

export interface AuditLogListOut {
  items: AuditLogOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilterOptions {
  resource_types: string[];
  actions: string[];
  statuses: ("SUCCESS" | "FAILED")[];
}

export interface AuditQuery {
  page?: number;
  page_size?: number;
  resource_type?: string;
  action?: string;
  status?: string;
  user_email?: string;
  trace_id?: string;
  start_at?: string;
  end_at?: string;
}

function _qs(q: AuditQuery): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

export const adminAuditApi = {
  list: (q: AuditQuery = {}) =>
    api.get<AuditLogListOut>(`/api/v1/admin/audit-logs${_qs(q)}`),
  detail: (id: number) =>
    api.get<AuditLogOut>(`/api/v1/admin/audit-logs/${id}`),
  options: () =>
    api.get<AuditFilterOptions>("/api/v1/admin/audit-logs/_options"),
};
