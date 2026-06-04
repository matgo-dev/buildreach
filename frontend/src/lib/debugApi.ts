// /api/v1/_debug/* 调试接口客户端(v3 §12)。
import { api } from "./api";
import type { ResourceCode, Scope } from "@/config/permission-matrix";

export interface ScopeCheck {
  user: string;
  roles: string[];
  resource: ResourceCode;
  resource_name: string;
  permission_check: {
    required: string | null;
    passed: boolean;
    explanation: string;
  };
  scope_resolved: Scope;
  would_apply_filter: string;
  explanation: string;
}

export const debugApi = {
  scope: (resource: ResourceCode) =>
    api.get<ScopeCheck>(`/api/v1/_debug/scope?resource=${encodeURIComponent(resource)}`),
};
