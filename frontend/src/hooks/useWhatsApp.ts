"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useAuthStore } from "@/stores/authStore";
import { getApiBase } from "@/lib/env";

interface WhatsAppData {
  whatsapp_link: string | null;
  number: string | null;
}

export interface WhatsAppContext {
  /** 商品名称 */
  productName?: string;
  /** 商品 SKU / SPU 编号 */
  productCode?: string;
}

async function fetchWhatsApp(): Promise<WhatsAppData> {
  const res = await fetch(`${getApiBase()}/api/v1/contact/whatsapp`);
  const json = await res.json();
  return json.data;
}

/**
 * 从后端拉取客服 WhatsApp 链接和号码。
 * 公开端点,无需登录;SWR 缓存,不重复请求。
 *
 * buildLink(ctx?) — 根据当前登录态和传入的商品上下文拼带预填文案的链接:
 *   未登录 + 非商品页 → 纯链接
 *   未登录 + 商品页   → Hi, I'm interested in [商品名]
 *   已登录 + 非商品页 → Hi, I'm [用户名/公司名]
 *   已登录 + 商品页   → Hi, I'm [用户名/公司名], I'm interested in [商品名]
 */
export function useWhatsApp() {
  const { data } = useSWR<WhatsAppData>(
    "/api/v1/contact/whatsapp",
    fetchWhatsApp,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  const user = useAuthStore((s) => s.user);

  const buildLink = useCallback(
    (ctx?: WhatsAppContext): string | null => {
      const baseLink = data?.whatsapp_link;
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
      // whatsapp_link 格式: https://wa.me/xxx 或 https://api.whatsapp.com/send?phone=xxx
      const separator = baseLink.includes("?") ? "&" : "?";
      return `${baseLink}${separator}text=${encodeURIComponent(text)}`;
    },
    [data?.whatsapp_link, user],
  );

  return {
    link: data?.whatsapp_link ?? null,
    number: data?.number ?? null,
    configured: !!data?.whatsapp_link,
    buildLink,
  };
}
