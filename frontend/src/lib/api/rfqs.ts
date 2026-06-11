// 买方询价单 API client
//
// 后端契约: backend/app/api/v1/rfqs.py
// 买方视角返回 RfqBuyerPublic（不含内部字段）

import { api } from "../api";

// ---------- 请求类型 ----------

export type SourceType = "CART" | "DIRECT";

export interface RfqDirectItem {
  sku_id: number;
  quantity: number;
  target_unit_price?: number;
  remark?: string;
}

export interface RfqCreate {
  source_type: SourceType;
  cart_item_ids?: number[];
  items?: RfqDirectItem[]; // 本期只实现 CART 路径，BUYER DIRECT 留 TODO；后端已支持
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  requested_delivery_place?: string;
  expected_delivery_date?: string; // UTC ISO datetime: "YYYY-MM-DDT00:00:00Z"
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
  sku_id: number;
  product_name_snapshot: string | null;
  sku_spec_snapshot: string | null;
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
export async function createRfq(data: RfqCreate): Promise<RfqBuyerPublic> {
  return api.post<RfqBuyerPublic>("/api/v1/rfqs", data);
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

/** 买方撤回改单：SUBMITTED → DRAFT */
export async function withdrawRfq(rfqId: number): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/withdraw`, {});
}

/** 草稿态编辑行项数量 */
export async function updateRfqItemQty(
  rfqId: number,
  itemId: number,
  quantity: number,
): Promise<RfqBuyerPublic> {
  return api.patch<RfqBuyerPublic>(`/api/v1/rfqs/${rfqId}/items/${itemId}`, { quantity });
}
