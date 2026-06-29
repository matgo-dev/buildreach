"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useAuthStore } from "@/stores/authStore";
import { getApiBase } from "@/lib/env";

/** 后端 /api/v1/contact/info 返回的完整联系方式 */
interface ContactInfo {
  whatsapp_link: string | null;
  whatsapp_number: string | null;
  email: string | null;
}

export interface WhatsAppContext {
  /** 商品名称 */
  productName?: string;
  /** 商品 SKU / SPU 编号 */
  productCode?: string;
}

const CONTACT_KEY = "/api/v1/contact/info";

async function fetchContactInfo(): Promise<ContactInfo> {
  const res = await fetch(`${getApiBase()}${CONTACT_KEY}`);
  const json = await res.json();
  return json.data;
}

/**
 * 平台联系方式(WhatsApp + 邮箱)。
 * 公开端点,无需登录;SWR 同 key 去重,全站只请求一次。
 */
export function useContactInfo() {
  const { data } = useSWR<ContactInfo>(
    CONTACT_KEY,
    fetchContactInfo,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  return {
    whatsappLink: data?.whatsapp_link ?? null,
    whatsappNumber: data?.whatsapp_number ?? null,
    email: data?.email ?? null,
    configured: !!data?.whatsapp_link || !!data?.email,
  };
}

/**
 * WhatsApp 专用 hook — 在 useContactInfo 基础上提供 buildLink 能力。
 *
 * buildLink(ctx?) — 根据当前登录态和商品上下文拼带预填文案的链接:
 *   未登录 + 非商品页 → 纯链接
 *   未登录 + 商品页   → Hi, I'm interested in [商品名]
 *   已登录 + 非商品页 → Hi, I'm [用户名/公司名]
 *   已登录 + 商品页   → Hi, I'm [用户名/公司名], I'm interested in [商品名]
 */
export function useWhatsApp() {
  const contact = useContactInfo();
  const user = useAuthStore((s) => s.user);

  const buildLink = useCallback(
    (ctx?: WhatsAppContext): string | null => {
      const baseLink = contact.whatsappLink;
      if (!baseLink) return null;

      const parts: string[] = [];

      // 用户身份
      const userName = user?.name || user?.username;
      const orgName = user?.organization?.name;
      if (userName && orgName) {
        parts.push(`I'm ${userName} from ${orgName}`);
      } else if (userName) {
        parts.push(`I'm ${userName}`);
      } else if (orgName) {
        parts.push(`I'm from ${orgName}`);
      }

      // 商品信息
      if (ctx?.productName) {
        const product = ctx.productCode
          ? `${ctx.productName} (${ctx.productCode})`
          : ctx.productName;
        parts.push(`I'm interested in ${product}`);
      }

      if (parts.length === 0) return baseLink;

      const text = `Hi, ${parts.join(", ")}`;
      const separator = baseLink.includes("?") ? "&" : "?";
      return `${baseLink}${separator}text=${encodeURIComponent(text)}`;
    },
    [contact.whatsappLink, user],
  );

  return {
    link: contact.whatsappLink,
    number: contact.whatsappNumber,
    email: contact.email,
    configured: !!contact.whatsappLink,
    buildLink,
  };
}
