// 报价 API client
//
// 后端契约: backend/app/api/v1/quotes.py
// 运营视角返回 RfqQuoteOperatorView

import { api } from "../api";

// ---------- 枚举码镜像（与后端 quote_terms.py 同源）----------

export const TRADE_TERMS = ["FOB", "CFR", "CIF"] as const;
export const CURRENCIES = ["USD", "CNY", "TZS"] as const;
export type TradeTerm = (typeof TRADE_TERMS)[number];
export type Currency = (typeof CURRENCIES)[number];

// ---------- 请求类型 ----------

export interface QuoteTierInput {
  min_qty: number; // > 0
  unit_price: number; // >= 0
}

export interface QuoteLineInput {
  rfq_item_id: number;
  unit_price: number; // >= 0, 必填
  moq?: number; // > 0
  cbm_per_unit?: number; // >= 0
  gross_weight_per_unit?: number; // >= 0
  tiers?: QuoteTierInput[];
}

export interface QuoteHeaderInput {
  trade_term?: TradeTerm;
  named_place?: string;
  currency?: Currency;
  valid_until?: string; // UTC ISO datetime
  lead_time_days?: number; // >= 0
  eta_days?: number; // >= 0
}

export interface QuoteCreatePayload {
  header: QuoteHeaderInput;
  lines: QuoteLineInput[];
}

// ---------- 响应类型 ----------

export interface QuoteTierPublic {
  min_qty: number;
  unit_price: number;
}

export interface QuoteItemOperatorView {
  id: number;
  rfq_item_id: number;
  unit_price: number | null;
  moq: number | null;
  cbm_per_unit: number | null;
  gross_weight_per_unit: number | null;
  line_amount: number | null;
  tiers: QuoteTierPublic[];
  cost: unknown | null; // 本轮不渲染
}

export interface RfqQuoteOperatorView {
  id: number;
  quote_no: string;
  version: number;
  quote_status: string; // ACTIVE | SUPERSEDED
  quoted_by_user_id: number | null;
  quoted_at: string | null;
  trade_term: string | null;
  named_place: string | null;
  currency: string | null;
  valid_until: string | null;
  lead_time_days: number | null;
  eta_days: number | null;
  total_amount: number | null;
  created_at: string | null;
  items: QuoteItemOperatorView[];
}

// ---------- 买方响应类型 ----------

export interface QuoteItemBuyerPublic {
  id: number;
  rfq_item_id: number;
  unit_price: number | null;
  moq: number | null;
  cbm_per_unit: number | null;
  gross_weight_per_unit: number | null;
  line_amount: number | null;
  tiers: QuoteTierPublic[];
}

export interface RfqQuoteBuyerPublic {
  id: number;
  quote_no: string;
  trade_term: string | null;
  named_place: string | null;
  currency: string | null;
  valid_until: string | null;
  lead_time_days: number | null;
  eta_days: number | null;
  total_amount: number | null;
  items: QuoteItemBuyerPublic[];
}

export interface RfqDecisionResult {
  rfq_id: number;
  status: string;
  accepted_quote_id?: number;
}

// ---------- API 函数 ----------

/** 回填/创建报价 */
export async function backfillQuote(
  rfqId: number,
  payload: QuoteCreatePayload,
): Promise<RfqQuoteOperatorView> {
  return api.post<RfqQuoteOperatorView>(
    `/api/v1/rfqs/${rfqId}/quotes`,
    payload,
  );
}

/** 查询报价列表（运营视角） */
export async function listQuotes(
  rfqId: number,
): Promise<RfqQuoteOperatorView[]> {
  return api.get<RfqQuoteOperatorView[]>(`/api/v1/rfqs/${rfqId}/quotes`);
}

/** 查询报价列表（买方视角，仅 ACTIVE，0/1 条） */
export async function listBuyerQuotes(
  rfqId: number,
): Promise<RfqQuoteBuyerPublic[]> {
  return api.get<RfqQuoteBuyerPublic[]>(`/api/v1/rfqs/${rfqId}/quotes`);
}

/** 接受报价 */
export async function acceptRfq(
  rfqId: number,
): Promise<RfqDecisionResult> {
  return api.patch<RfqDecisionResult>(`/api/v1/rfqs/${rfqId}/accept`, {});
}

/** 拒绝报价 */
export async function rejectRfq(
  rfqId: number,
): Promise<RfqDecisionResult> {
  return api.patch<RfqDecisionResult>(`/api/v1/rfqs/${rfqId}/reject`, {});
}
