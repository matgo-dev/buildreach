// /api/v1/auth/me/organization/members 客户端(买方组织 owner 成员管理)
//
// 后端契约见 backend/app/api/v1/auth.py(list_my_members 等)与 schemas/me.py

import { api } from "./api";

export interface MemberOut {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  status: "ACTIVE" | "DISABLED";
  is_owner: boolean;
  created_at: string;
}

export interface MemberCreateIn {
  name: string;
  email: string;
  password: string;
}

const BASE = "/api/v1/auth/me/organization/members";

export const orgMembersApi = {
  list: () => api.get<MemberOut[]>(BASE),
  create: (body: MemberCreateIn) => api.post<MemberOut>(BASE, body),
  disable: (userId: number) => api.post<MemberOut>(`${BASE}/${userId}/disable`),
  enable: (userId: number) => api.post<MemberOut>(`${BASE}/${userId}/enable`),
};
