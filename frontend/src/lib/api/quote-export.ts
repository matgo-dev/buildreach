/**
 * 报价单 PDF 导出。
 *
 * 不能用 apiRequest(它 .json() 解析),但 token/header 注入
 * 必须与 lib/api.ts 的 rawFetch 一致。
 *
 * 预生成产物改造后，下载端点可能返回：
 * - 200 + application/pdf → 正常下载
 * - 202 + JSON → 产物正在生成中
 * - 422 + JSON → 产物生成失败
 */

import { useAuthStore } from "@/stores/authStore";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** 下载结果类型 */
export type ExportResult =
  | { status: "ok" }
  | { status: "generating"; message: string }
  | { status: "failed"; message: string };

function _buildHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  const lang =
    typeof document !== "undefined"
      ? document.documentElement.lang || "zh"
      : "zh";
  const sid =
    typeof window !== "undefined"
      ? sessionStorage.getItem("x-session-id") || ""
      : "";

  return {
    "Accept-Language": lang,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(sid ? { "X-Session-Id": sid } : {}),
  };
}

export async function exportQuotePdf(rfqId: number): Promise<ExportResult> {
  const headers = _buildHeaders();

  const resp = await fetch(
    `${BASE}/api/v1/rfqs/${rfqId}/quote/export`,
    { headers, credentials: "include" },
  );

  const ct = resp.headers.get("content-type") || "";

  // 202 → 产物正在生成中
  if (resp.status === 202 && ct.includes("application/json")) {
    const body = await resp.json();
    return { status: "generating", message: body.message || "generating" };
  }

  // 422 → 产物生成失败
  if (resp.status === 422 && ct.includes("application/json")) {
    const body = await resp.json();
    return { status: "failed", message: body.message || "failed" };
  }

  // 其他非 2xx 错误
  if (!resp.ok) {
    if (ct.includes("application/json")) {
      const body = await resp.json();
      const err = new Error(body.message || `Export failed: ${resp.status}`);
      (err as Record<string, unknown>).messageKey = body.message_key;
      (err as Record<string, unknown>).code = body.code;
      throw err;
    }
    throw new Error(`Export failed: ${resp.status}`);
  }

  // 200 + application/pdf → 正常触发浏览器下载
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

  return { status: "ok" };
}
