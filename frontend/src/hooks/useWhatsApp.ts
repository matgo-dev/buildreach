"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";

/** 后端 /api/v1/contact/info 的结构 */
interface ContactConfig {
  whatsapp_link: string | null;
  whatsapp_number: string | null;
  wechat_id: string | null;
  wechat_qr_image: string | null;
  email: string | null;
}

export interface WhatsAppContext {
  /** 商品名称 */
  productName?: string;
  /** 商品 SKU / SPU 编号 */
  productCode?: string;
}

const CONTACT_CONFIG_PATH = "/api/v1/contact/info";

async function fetchContactConfig(): Promise<ContactConfig> {
  return api.get<ContactConfig>(CONTACT_CONFIG_PATH, { noAuth: true });
}

/**
 * 将 WhatsApp 号码规范化为 wa.me 链接。
 * 逻辑从后端 resolve_whatsapp_link() 迁移过来。
 */
function resolveWhatsAppLink(raw: string | undefined | null): string | null {
  if (!raw?.trim()) return null;
  // 去掉非数字字符
  let digits = raw.replace(/\D/g, "");
  // 去掉国际冠码 00
  if (digits.startsWith("00")) digits = digits.slice(2);
  return digits ? `https://wa.me/${digits}` : null;
}

/**
 * 平台联系方式（WhatsApp + WeChat + 邮箱）。
 * 从后端公开接口读取，配置由服务端运行时环境变量注入。
 * SWR 同 key 去重，全站只请求一次。
 */
export function useContactInfo() {
  const { data, isLoading } = useSWR<ContactConfig>(
    CONTACT_CONFIG_PATH,
    fetchContactConfig,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  const whatsappLink = data?.whatsapp_link || resolveWhatsAppLink(data?.whatsapp_number);

  return {
    isLoading,
    whatsappLink,
    whatsappNumber: data?.whatsapp_number?.trim() || null,
    wechatId: data?.wechat_id?.trim() || null,
    wechatQrImage: data?.wechat_qr_image?.trim() || null,
    email: data?.email?.trim() || null,
    configured: !!whatsappLink || !!data?.email,
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
