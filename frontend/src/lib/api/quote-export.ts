/**
 * 报价单 PDF 导出。
 *
 * 不能用 apiRequest(它 .json() 解析),但 token/header 注入
 * 必须与 lib/api.ts 的 rawFetch 一致。
 */

import { useAuthStore } from "@/stores/authStore";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function exportQuotePdf(rfqId: number): Promise<void> {
  const token = useAuthStore.getState().accessToken;

  // 对齐 rawFetch:Accept-Language + credentials + X-Session-Id
  const lang =
    typeof document !== "undefined"
      ? document.documentElement.lang || "zh"
      : "zh";
  const sid =
    typeof window !== "undefined"
      ? sessionStorage.getItem("x-session-id") || ""
      : "";

  const headers: Record<string, string> = {
    "Accept-Language": lang,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(sid ? { "X-Session-Id": sid } : {}),
  };

  const resp = await fetch(
    `${BASE}/api/v1/rfqs/${rfqId}/quote/export`,
    { headers, credentials: "include" },
  );

  if (!resp.ok) {
    // 尝试解析业务错误 JSON
    const ct = resp.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      const body = await resp.json();
      const err = new Error(body.message || `Export failed: ${resp.status}`);
      // 挂 messageKey 供调用方 i18n 翻译
      (err as any).messageKey = body.message_key;
      (err as any).code = body.code;
      throw err;
    }
    throw new Error(`Export failed: ${resp.status}`);
  }

  // blob → 触发浏览器下载
  const blob = await resp.blob();
  const disposition = resp.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] || `Quotation_${rfqId}.pdf`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
