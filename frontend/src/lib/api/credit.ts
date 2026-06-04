// /api/v1/credit 客户端
//
// 后端契约见 backend/app/api/v1/credit.py
// 技术方案 §四

import { api } from "../api";

export type Grade = "A" | "B" | "C" | "D";

export interface CompanyListItem {
  id: number;
  name: string;
  legal_name_en: string | null;
  country_code: string;
  registration_no: string | null;
  total_score: number | null;
  grade: Grade | null;
}

export interface DimensionOut {
  code: string;
  name: string;
  max_score: number;
  score: number;
}

export interface ScoreDetailOut {
  dimension_code: string;
  dimension_name: string;
  subitem_code: string;
  subitem_name: string;
  score: number;
  max_score: number;
  hit_rule_code: string | null;
  hit_rule_description: string | null;
  is_default_score: boolean;
}

export interface DimensionOverrideHit {
  dimension_code: string;
  override_rule_code: string;
  override_description: string;
  natural_score: number;
  final_score: number;
}

export interface SnapshotOut {
  id: number;
  total_score: number;
  grade: Grade;
  /** 后端数据契约保留字段,本期前端不消费(v0.2-Δ2 回滚后:UI 不展示 natural/override) */
  dimension_1_natural_score: number | null;
  /** 同上 */
  dimension_2_natural_score: number | null;
  /** 同上 */
  dimension_3_natural_score: number | null;
  /** 同上 */
  dimension_4_natural_score: number | null;
  /** 同上;数组形态 */
  dimension_overrides: DimensionOverrideHit[] | null;
  rule_version: number;
  trigger_type: string;
  ai_summary: string | null;
  ai_summary_generated_at: string | null;
  is_current: boolean;
  calculated_at: string;
}

export interface BasicDataOut {
  established_date: string | null;
  registered_capital: string | null;
  business_scope: string | null;
  legal_representative: string | null;
  shareholders: string | null;
  status_text: string | null;
  address: string | null;
  website: string | null;
  data_source: string;
  fetched_at: string | null;
}

export interface FinanceDataOut {
  revenue_trend: string | null;
  debt_ratio: string | null; // Decimal 序列化为字符串
  cash_flow_status: string | null;
  data_source: string;
  fetched_at: string | null;
}

export interface LegalDataOut {
  litigation_count: number;
  defaulter_unresolved_count: number;
  defaulter_resolved_count: number;
  negative_news_level: string | null;
  data_source: string;
  fetched_at: string | null;
}

export interface CertificationOut {
  id: number;
  cert_type: "mandatory_country" | "system_general" | "industry_specific";
  cert_name: string;
  target_country_code: string | null;
  issuer: string | null;
  issued_at: string | null;
  expires_at: string | null;
  status: "valid" | "expired" | "suspicious_forged";
  data_source: string;
}

export interface CompanyDetailOut {
  id: number;
  name: string;
  legal_name_en: string | null;
  country_code: string;
  registration_no: string | null;
  snapshot: SnapshotOut | null;
  dimensions: DimensionOut[];
  details: ScoreDetailOut[];
  basic: BasicDataOut | null;
  finance: FinanceDataOut | null;
  legal: LegalDataOut | null;
  certifications: CertificationOut[];
}

export interface SearchHistoryItem {
  id: number;
  company_id: number;
  company_name: string;
  country_code: string;
  grade: Grade | null;
  searched_at: string;
}

export interface AiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  created_at: string;
}

export interface AiConversation {
  id: number;
  user_id: number;
  company_id: number;
  started_at: string;
  messages: AiMessage[];
}

export const creditApi = {
  /** 搜索候选企业。 */
  search: (params: { country?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params.country) qs.set("country", params.country);
    if (params.q) qs.set("q", params.q);
    return api.get<CompanyListItem[]>(
      `/api/v1/credit/companies/search?${qs.toString()}`
    );
  },

  /** 企业详情(首访可能触发 ai_summary 同步生成,响应可能稍慢)。 */
  detail: (companyId: number) =>
    api.get<CompanyDetailOut>(`/api/v1/credit/companies/${companyId}`),

  /** 单家重算(OPERATOR / ADMIN)。 */
  recompute: (companyId: number) =>
    api.post<SnapshotOut>(`/api/v1/credit/companies/${companyId}/recompute`),

  /** 当前用户最近 5 条搜索历史。 */
  history: () => api.get<SearchHistoryItem[]>("/api/v1/credit/search-history"),

  /** 删除一条历史。 */
  deleteHistory: (id: number) =>
    api.delete<{ deleted: number }>(`/api/v1/credit/search-history/${id}`),

  /** 创建 AI 会话。 */
  createConversation: (companyId: number) =>
    api.post<AiConversation>("/api/v1/credit/ai/conversations", {
      company_id: companyId,
    }),

  /** 获取会话历史。 */
  getConversation: (id: number) =>
    api.get<AiConversation>(`/api/v1/credit/ai/conversations/${id}`),
};

/** SSE 流式发送消息。每收到一段 chunk 调 onChunk;[DONE] 或 error 时调 onDone。
 *
 * 直接 fetch 走 ReadableStream(避免 EventSource 不能带 Authorization 头)。
 */
export async function streamAiMessage(
  conversationId: number,
  content: string,
  callbacks: {
    onChunk?: (chunk: string) => void;
    onDone?: () => void;
    onError?: (msg: string) => void;
  }
): Promise<void> {
  const { useAuthStore } = await import("@/stores/authStore");
  const accessToken = useAuthStore.getState().accessToken;
  const BASE =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const resp = await fetch(
    `${BASE}/api/v1/credit/ai/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      credentials: "include",
      body: JSON.stringify({ content }),
    }
  );

  if (!resp.ok) {
    callbacks.onError?.(`HTTP ${resp.status}`);
    return;
  }
  const reader = resp.body?.getReader();
  if (!reader) {
    callbacks.onError?.("无响应流");
    return;
  }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE 帧间用 \n\n 分隔
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      // 解析帧:可能是 "event: error\ndata: ..." 或 "data: ..."
      const lines = frame.split("\n");
      let evt = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) evt = line.slice(7);
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (evt === "error") {
        try {
          const parsed = JSON.parse(data);
          callbacks.onError?.(parsed.error || "未知错误");
        } catch {
          callbacks.onError?.(data || "未知错误");
        }
        callbacks.onDone?.();
        return;
      }
      if (data === "[DONE]") {
        callbacks.onDone?.();
        return;
      }
      // 反转义 \n
      callbacks.onChunk?.(data.replace(/\\n/g, "\n"));
    }
  }
  callbacks.onDone?.();
}
