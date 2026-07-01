"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

/** 后端 /api/v1/config 的结构 */
export interface PublicConfig {
  contact: {
    whatsapp_link: string | null;
    whatsapp_number: string | null;
    wechat_id: string | null;
    wechat_qr_image: string | null;
    email: string | null;
  };
  auth: {
    require_email_verification: boolean;
  };
}

const PUBLIC_CONFIG_PATH = "/api/v1/config";

async function fetchPublicConfig(): Promise<PublicConfig> {
  return api.get<PublicConfig>(PUBLIC_CONFIG_PATH, { noAuth: true });
}

/**
 * 前端公开运行时配置(联系方式 + 功能开关)的唯一数据源。
 * SWR 同 key 去重 —— 全站所有派生 hook(useContactInfo / useAuthConfig)共享一次请求。
 */
export function usePublicConfig() {
  const { data, isLoading } = useSWR<PublicConfig>(
    PUBLIC_CONFIG_PATH,
    fetchPublicConfig,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );
  return { data, isLoading };
}

/**
 * 买方注册是否要求邮箱验证码。派生自统一公开配置，与 useContactInfo 共享请求。
 * 加载完成前 requireEmailVerification 为 undefined —— 调用方应在 isLoading 时禁用相关操作。
 */
export function useAuthConfig() {
  const { data, isLoading } = usePublicConfig();
  return {
    isLoading,
    requireEmailVerification: data?.auth?.require_email_verification,
  };
}
