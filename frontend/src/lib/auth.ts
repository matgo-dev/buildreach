// 认证相关类型与 API 调用。

import type { CountryCode, LanguageCode } from "@/config/country-registration-rules";
import { api } from "./api";

export type RoleCode = "BUYER" | "SUPPLIER" | "OPERATOR" | "ADMIN";

export interface OrganizationInfo {
  type: "BUYER_ORG" | "SUPPLIER_ORG";
  id: number;
  name: string;
  is_owner: boolean;
  /** SupplierOrg.status / BuyerOrg.status,前端 dashboard banner 显示判定用 */
  status?: string | null;
}

export interface MeData {
  id: number;
  email: string;
  username: string | null;
  name: string;
  phone: string | null;
  status: "ACTIVE" | "DISABLED";
  must_change_password: boolean;
  roles: RoleCode[];
  permissions: string[];
  organization: OrganizationInfo | null;
  /** 用户语言偏好(SUPPLIER 注册时写入,其他场景为 null;TODO(T-LANG-CHANGE) 自助切换入口) */
  language_preference?: string | null;
}

export interface LoginResult {
  /** access token,前端存 Zustand 内存 */
  access_token: string;
  token_type: string;
  expires_in: number;
  /** refresh token 由后端通过 httpOnly cookie 下发,前端 JS 读不到 */
}

export const authApi = {
  registerSupplier: (payload: {
    email: string;
    name: string;
    /** SUPPLIER 注册 phone 必填(PRD v1.3 §2.2) */
    phone: string;
    password: string;
    company_name: string;
    country_code: CountryCode;
    registration_no: string;
    language_preference: LanguageCode;
  }) =>
    api.post<{ user_id: number; email: string }>(
      "/api/v1/auth/register/supplier",
      payload,
      { noAuth: true }
    ),

  registerBuyer: (payload: {
    email: string;
    username?: string;
    name: string;
    phone?: string;
    password: string;
    company_name: string;
    unified_social_credit_code: string;
  }) =>
    api.post<{ user_id: number; email: string }>(
      "/api/v1/auth/register/buyer",
      payload,
      { noAuth: true }
    ),

  /** identifier 可为邮箱或用户名 */
  login: (identifier: string, password: string) =>
    api.post<LoginResult>("/api/v1/auth/login", { identifier, password }, { noAuth: true }),

  me: () => api.get<MeData>("/api/v1/auth/me"),

  logout: () => api.post<null>("/api/v1/auth/logout"),

  changePassword: (old_password: string, new_password: string) =>
    api.post<null>("/api/v1/auth/change-password", { old_password, new_password }),

  // ----- 自助资料 -----

  updateProfile: (payload: { name?: string; phone?: string | null }) =>
    api.patch<MeBasic>("/api/v1/auth/me/profile", payload),

  changeEmail: (new_email: string, current_password: string) =>
    api.post<MeBasic>("/api/v1/auth/me/email", { new_email, current_password }),

  changeUsername: (new_username: string | null, current_password: string) =>
    api.post<MeBasic>("/api/v1/auth/me/username", { new_username, current_password }),

  changePhone: (new_phone: string | null, current_password: string) =>
    api.post<MeBasic>("/api/v1/auth/me/phone", { new_phone, current_password }),
};

/** /me/* 接口返回的简版 user(不含 roles/permissions/organization) */
export interface MeBasic {
  id: number;
  email: string;
  username: string | null;
  name: string;
  phone: string | null;
  status: "ACTIVE" | "DISABLED";
  must_change_password: boolean;
}

// 登录后跳转逻辑见 src/config/navigation.ts → defaultDashboardOf
