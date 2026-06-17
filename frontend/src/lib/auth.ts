// 认证相关类型与 API 调用。

import type { CountryCode, LanguageCode } from "@/config/country-registration-rules";
import { api, ApiError } from "./api";

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

  registerBuyer: async (payload: {
    phone: string;
    phone_region?: string;
    password: string;
    name: string;
    company_name: string;
    address: string;
    business_category_codes: string[];
    email?: string;
    tin?: string;
    brela_no?: string;
    storefront_images: File[];
    license_images?: File[];
    language_preference?: string;
  }): Promise<LoginResult> => {
    const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    const fd = new FormData();
    fd.append("phone", payload.phone);
    fd.append("phone_region", payload.phone_region || "TZ");
    fd.append("password", payload.password);
    fd.append("name", payload.name);
    fd.append("company_name", payload.company_name);
    fd.append("address", payload.address);
    for (const code of payload.business_category_codes) {
      fd.append("business_category_codes", code);
    }
    if (payload.email) fd.append("email", payload.email);
    if (payload.tin) fd.append("tin", payload.tin);
    if (payload.brela_no) fd.append("brela_no", payload.brela_no);
    if (payload.language_preference) fd.append("language_preference", payload.language_preference);
    for (const file of payload.storefront_images) {
      fd.append("storefront_images", file);
    }
    if (payload.license_images) {
      for (const file of payload.license_images) {
        fd.append("license_images", file);
      }
    }
    // multipart/form-data: 不设 Content-Type,让浏览器自动加 boundary
    const lang = typeof document !== "undefined" ? document.documentElement.lang || "zh" : "zh";
    const res = await fetch(`${BASE}/api/v1/auth/register/buyer`, {
      method: "POST",
      headers: { "Accept-Language": lang },
      credentials: "include",
      body: fd,
    });
    const json = await res.json();
    if (!res.ok || json.code !== 0) {
      throw new ApiError({
        code: json?.code ?? res.status * 100,
        message: json?.message ?? res.statusText ?? "Registration failed",
        status: res.status,
        traceId: json?.trace_id,
        data: json?.data,
        messageKey: json?.message_key,
        messageParams: json?.message_params,
      });
    }
    return json.data as LoginResult;
  },

  /** identifier 可为邮箱、手机号或用户名 */
  login: (identifier: string, password: string, phoneRegion?: string) =>
    api.post<LoginResult>(
      "/api/v1/auth/login",
      { identifier, password, phone_region: phoneRegion || undefined },
      { noAuth: true },
    ),

  me: () => api.get<MeData>("/api/v1/auth/me"),

  logout: () => api.post<null>("/api/v1/auth/logout"),

  changePassword: (old_password: string, new_password: string) =>
    api.post<null>("/api/v1/auth/change-password", { old_password, new_password }),

  // ----- 自助资料 -----

  updateProfile: (payload: { name?: string; email?: string; phone?: string | null; phone_region?: string; username?: string | null }) =>
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
