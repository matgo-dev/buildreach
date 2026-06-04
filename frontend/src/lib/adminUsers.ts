// /api/v1/admin/users 客户端
//
// 后端契约见 backend/app/api/v1/admin_users.py 与 schemas/user.py

import { api } from "./api";
import type { RoleCode } from "./auth";

export type UserStatus = "ACTIVE" | "DISABLED";
export type InternalRole = "ADMIN" | "OPERATOR";

export interface AdminUserOut {
  id: number;
  email: string;
  username: string | null;
  name: string;
  status: UserStatus;
  must_change_password: boolean;
  roles: RoleCode[];
}

export interface AdminUserListOut {
  items: AdminUserOut[];
  total: number;
}

export interface AdminUserCreateIn {
  email: string;
  username?: string;
  name: string;
  password: string;
  role: InternalRole;
  must_change_password?: boolean;
}

export const adminUsersApi = {
  list: (page = 1, page_size = 50) =>
    api.get<AdminUserListOut>(
      `/api/v1/admin/users?page=${page}&page_size=${page_size}`
    ),
  create: (body: AdminUserCreateIn) =>
    api.post<AdminUserOut>("/api/v1/admin/users", body),
  disable: (userId: number) =>
    api.post<AdminUserOut>(`/api/v1/admin/users/${userId}/disable`),
  enable: (userId: number) =>
    api.post<AdminUserOut>(`/api/v1/admin/users/${userId}/enable`),
};
