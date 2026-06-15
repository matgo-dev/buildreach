// 买方询价单 API client
//
// 后端契约: backend/app/api/v1/rfqs.py
// 买方视角返回 RfqBuyerPublic（不含内部字段）

import { api } from "../api";

// ---------- 请求类型 ----------

export interface RfqItemInput {
  product_id: number;
  selected_variants?: Array<{ attr_name: string; value: string }>;
  quantity: number;
  target_unit_price?: number;
  remark?: string;
}

export interface RfqCreate {
  items: RfqItemInput[];
  as_draft?: boolean;
  buyer_org_id?: number;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  requested_delivery_place?: string;
  expected_delivery_date?: string;
  target_currency?: string;
  required_certifications?: string[];
  attachment_urls?: string[];
  remark?: string;
}

export interface RfqUpdatePayload {
  items: RfqItemInput[];
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  requested_delivery_place?: string;
  expected_delivery_date?: string;
  target_currency?: string;
  required_certifications?: string[];
  attachment_urls?: string[];
  remark?: string;
}

export interface RfqListQuery {
  page?: number;
  page_size?: number;
  status?: string;
  mine?: boolean;
}

// ---------- 响应类型 ----------

export interface RfqItemPublic {
  id: number;
  product_id: number;
  variant_snapshot: Array<{ attr_name: string; value: string }>;
  variant_display: string | null;
  product_name_snapshot: string | null;
  uom_snapshot: string | null;
  quantity: number;
  target_unit_price: number | null;
  remark: string | null;
}

export interface RfqBuyerPublic {
  id: number;
  rfq_no: string;
  status: string; // DRAFT | SUBMITTED | PROCESSING | QUOTED | ACCEPTED | REJECTED | EXPIRED | CANCELLED
  source: string; // BUYER_SELF | OPERATOR_PROXY
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  remark: string | null;
  requested_delivery_place: string | null;
  expected_delivery_date: string | null;
  target_currency: string | null;
  required_certifications: string[] | null;
  attachment_urls: string[] | null;
  created_at: string | null;
  updated_at: string | null;
  items: RfqItemPublic[];
}

/** 运营全量视图，含内部字段 */
export interface RfqOperatorView extends RfqBuyerPublic {
  buyer_org_id: number;
  buyer_user_id: number | null;
  created_by_user_id: number;
  operator_assignee_id: number | null;
  cancel_reason: string | null;
}

export interface RfqListResponse {
  items: RfqBuyerPublic[];
  total: number;
  page: number;
  page_size: number;
}

// ---------- API 函数 ----------

/** 创建询价单 */
export async function createRfq(
  data: RfqCreate,
  idempotencyKey?: string,
): Promise<RfqBuyerPublic> {
  return api.post<RfqBuyerPublic>("/api/v1/rfqs", data, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

/** 询价单列表 */
export async function listRfqs(
  params: RfqListQuery = {}
): Promise<RfqListResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.status) qs.set("status", params.status);
  if (params.mine) qs.set("mine", "true");
  const q = qs.toString();
  return api.get<RfqListResponse>(`/api/v1/rfqs${q ? `?${q}` : ""}`);
}

/** 询价单详情 */
export async function getRfq(rfqId: number): Promise<RfqBuyerPublic> {
  return api.get<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}`);
}

/** 取消询价单 */
export async function cancelRfq(
  rfqId: number,
  cancelReason?: string
): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/cancel`, cancelReason ? { cancel_reason: cancelReason } : {});
}

/** 运营受理询价单：SUBMITTED → PROCESSING */
export async function claimRfq(rfqId: number): Promise<RfqOperatorView> {
  return api.patch<RfqOperatorView>(`/api/v1/rfqs/${rfqId}/claim`, {});
}

/** 买方提交草稿：DRAFT → SUBMITTED */
export async function submitRfq(rfqId: number): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/submit`, {});
}

/** 买方撤回改单：SUBMITTED → DRAFT */
export async function withdrawRfq(rfqId: number): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/withdraw`, {});
}

/** 草稿态整单更新 */
export async function updateRfq(
  rfqId: number,
  data: RfqUpdatePayload,
): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}`, data);
}

/** 编辑行项数量（DRAFT 买方 / PROCESSING 运营） */
export async function updateRfqItemQty(
  rfqId: number,
  itemId: number,
  quantity: number,
): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/items/${itemId}`, { quantity });
}

// ── 运营行项增删改（PROCESSING 态） ──────────────────────

/** 添加询价行项（运营） */
export async function addRfqItem(
  rfqId: number,
  payload: RfqItemInput,
): Promise<RfqOperatorView> {
  return api.post<RfqOperatorView>(`/api/v1/rfqs/${rfqId}/items`, payload);
}

/** 编辑询价行项（运营） */
export async function editRfqItem(
  rfqId: number,
  itemId: number,
  payload: {
    selected_variants?: Array<{ attr_name: string; value: string }>;
    quantity?: number;
    target_unit_price?: number;
    remark?: string;
  },
): Promise<RfqOperatorView> {
  return api.put<RfqOperatorView>(`/api/v1/rfqs/${rfqId}/items/${itemId}`, payload);
}

/** 删除询价行项（运营） */
export async function deleteRfqItem(
  rfqId: number,
  itemId: number,
): Promise<RfqOperatorView> {
  return api.delete<RfqOperatorView>(`/api/v1/rfqs/${rfqId}/items/${itemId}`);
}
