"use client";

import useSWR from "swr";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface WhatsAppData {
  whatsapp_link: string | null;
  number: string | null;
}

async function fetchWhatsApp(): Promise<WhatsAppData> {
  const res = await fetch(`${BASE}/api/v1/contact/whatsapp`);
  const json = await res.json();
  return json.data;
}

/**
 * 从后端拉取客服 WhatsApp 链接和号码。
 * 公开端点,无需登录;SWR 缓存,不重复请求。
 */
export function useWhatsApp() {
  const { data } = useSWR<WhatsAppData>(
    "/api/v1/contact/whatsapp",
    fetchWhatsApp,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  return {
    link: data?.whatsapp_link ?? null,
    number: data?.number ?? null,
    configured: !!data?.whatsapp_link,
  };
}
