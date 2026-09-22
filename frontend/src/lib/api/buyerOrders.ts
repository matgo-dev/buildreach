// 买家「我的订单」API(matgo BFF → 履约后台)。
// 契约 docs/specs/2026-09-21-0214 §4.2 / §5.2:
//   - 金额与数量一律是 decimal string,展示时不做 Number() 转换。
//   - 响应二选一:{ binding } 状态,或履约 data 原样透传。
import { api } from "../api";

export type BindingState = "NO_ORG" | "AMBIGUOUS_ORG" | "ORG_DISABLED" | "NOT_BOUND";

export type OrderStage = "CONFIRMED" | "LOADED" | "IN_TRANSIT" | "ARRIVED" | "CANCELLED";
export type ShipmentStage = "LOADED" | "IN_TRANSIT" | "ARRIVED";
export type MilestoneType = "DEPARTED" | "TRANSSHIPMENT" | "ARRIVED";

export interface PortalOrderListItem {
  no: string;
  created_at: string;
  status: string;
  currency: string;
  total_amount: string;
  stage: OrderStage;
  line_count: number;
}

export interface PortalOrderLine {
  name_snapshot: string;
  spec_text_snapshot: string | null;
  unit_code: string;
  unit_label: string;
  qty: string;
  shipped_qty: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
}

export interface PortalMilestone {
  type: MilestoneType;
  event_at: string;
  location: string | null;
}

export interface PortalShipment {
  container_no: string;
  container_type: string;
  stage: ShipmentStage;
  loaded_at: string | null;
  etd: string | null;
  atd: string | null;
  eta: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
  milestones: PortalMilestone[];
}

export interface PortalOrderDetail extends PortalOrderListItem {
  lines: PortalOrderLine[];
  shipments: PortalShipment[];
}

export interface OrderPage {
  items: PortalOrderListItem[];
  total: number;
  page: number;
  size: number;
}

export type BindingResult = { kind: "binding"; binding: BindingState };
export type OrdersResult = BindingResult | { kind: "data"; page: OrderPage };
export type OrderDetailResult = BindingResult | { kind: "data"; order: PortalOrderDetail };

type BindingPayload = { binding: BindingState };

function isBinding(data: unknown): data is BindingPayload {
  return typeof data === "object" && data !== null && "binding" in data;
}

export async function getBuyerOrders(page: number, size: number): Promise<OrdersResult> {
  const data = await api.get<BindingPayload | OrderPage>(
    `/api/v1/buyer/orders?page=${page}&size=${size}`,
  );
  if (isBinding(data)) return { kind: "binding", binding: data.binding };
  return { kind: "data", page: data };
}

export async function getBuyerOrder(no: string): Promise<OrderDetailResult> {
  const data = await api.get<BindingPayload | PortalOrderDetail>(
    `/api/v1/buyer/orders/${encodeURIComponent(no)}`,
  );
  if (isBinding(data)) return { kind: "binding", binding: data.binding };
  return { kind: "data", order: data };
}

/**
 * decimal string → 带千分位的展示串。只做字符串操作,不经过 float(金额精度不可丢)。
 * "1234567.50" → "1,234,567.50";"-1200" → "-1,200";非法输入原样返回。
 */
export function formatDecimalString(value: string): string {
  const m = /^(-?)(\d+)(\.\d+)?$/.exec(value.trim());
  if (!m) return value;
  const [, sign, intPart, frac = ""] = m;
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${grouped}${frac}`;
}
