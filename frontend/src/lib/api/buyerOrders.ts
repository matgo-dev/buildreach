// 买家「我的订单」API(matgo BFF → 履约后台)。
// 契约 docs/specs/2026-09-21-0214 §4.2 / §5.2:
//   - 金额与数量一律是 decimal string,展示时不做 Number() 转换。
//   - 响应二选一:{ binding } 状态,或履约 data 原样透传。
import { api } from "../api";

export type BindingState = "NO_ORG" | "AMBIGUOUS_ORG" | "ORG_DISABLED" | "NOT_BOUND";

// 契约 §4.3:订单级全序 CONFIRMED < RECEIVED < LOADED < CLEARED < IN_TRANSIT < ARRIVED,CANCELLED 独立;
// 柜级全序 LOADED < CLEARED < IN_TRANSIT < ARRIVED。展示侧所有按阶段映射的表都用 Record<…> 键这两个联合,
// 履约新增阶段时先在这里补值,编译期即挡住漏项;运行期仍对不认识的值灰底兜底。
export type OrderStage = "CONFIRMED" | "RECEIVED" | "LOADED" | "CLEARED" | "IN_TRANSIT" | "ARRIVED" | "CANCELLED";
export type ShipmentStage = "LOADED" | "CLEARED" | "IN_TRANSIT" | "ARRIVED";
export type MilestoneType = "DEPARTED" | "TRANSSHIPMENT" | "ARRIVED";
/** 柜的报关状态:履约 customs_service.derive_status 单一源头派生,门户不重算。 */
export type CustomsStatus = "NONE" | "DECLARED" | "RELEASED";

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
  received_qty: string;          // 已入仓(库存入库 − 处置,履约派生);恒 ≥ shipped_qty
  shipped_qty: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
}

export interface PortalMilestone {
  type: MilestoneType;
  event_at: string;              // YYYY-MM-DD(纯日期,履约侧 date)
  location: string | null;
}

export interface PortalShipment {
  container_no: string | null;   // 履约侧可空(柜号未分配)
  container_type: string | null;
  stage: ShipmentStage;
  vessel_name: string | null;    // 船名 / 航次:航程信息,空则不显示
  voyage_no: string | null;
  customs_status: CustomsStatus;
  declared_at: string | null;    // 报关业务日期 YYYY-MM-DD
  released_at: string | null;
  loaded_at: string | null;      // UTC 时间戳
  etd: string | null;            // 以下三项 YYYY-MM-DD
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

function isOrderPage(data: unknown): data is OrderPage {
  return (
    typeof data === "object" && data !== null &&
    Array.isArray((data as OrderPage).items) && typeof (data as OrderPage).total === "number"
  );
}

function isOrderDetail(data: unknown): data is PortalOrderDetail {
  return (
    typeof data === "object" && data !== null &&
    typeof (data as PortalOrderDetail).no === "string" &&
    Array.isArray((data as PortalOrderDetail).lines) && Array.isArray((data as PortalOrderDetail).shipments)
  );
}

/** BFF 已保证 data 是对象;这里再守一层形状,不合规当"不可用"抛出,由页面落到重试面板而不是白屏。 */
export async function getBuyerOrders(page: number, size: number): Promise<OrdersResult> {
  const data = await api.get<unknown>(`/api/v1/buyer/orders?page=${page}&size=${size}`);
  if (isBinding(data)) return { kind: "binding", binding: data.binding };
  if (!isOrderPage(data)) throw new Error("malformed orders page");
  return { kind: "data", page: data };
}

export async function getBuyerOrder(no: string): Promise<OrderDetailResult> {
  const data = await api.get<unknown>(`/api/v1/buyer/orders/${encodeURIComponent(no)}`);
  if (isBinding(data)) return { kind: "binding", binding: data.binding };
  if (!isOrderDetail(data)) throw new Error("malformed order detail");
  return { kind: "data", order: data };
}

const DECIMAL_RE = /^(-?)(\d+)(?:\.(\d+))?$/;

/**
 * 比较两个 decimal string:a < b → -1,相等 → 0,a > b → 1;任一不是合法十进制串 → null(调用方按"事实未成立"处理)。
 * 只做字符串比较,不经过 float——"10.000" 与 "10" 相等,"9.999999999999999999" < "10" 不会被舍入成相等。
 */
export function compareDecimalStrings(a: string, b: string): -1 | 0 | 1 | null {
  const pa = DECIMAL_RE.exec(a.trim());
  const pb = DECIMAL_RE.exec(b.trim());
  if (!pa || !pb) return null;
  const norm = (m: RegExpExecArray) => {
    const int = m[2].replace(/^0+(?=\d)/, "");
    const frac = (m[3] ?? "").replace(/0+$/, "");
    const zero = /^0$/.test(int) && frac === "";
    return { neg: m[1] === "-" && !zero, int, frac };
  };
  const x = norm(pa);
  const y = norm(pb);
  if (x.neg !== y.neg) return x.neg ? -1 : 1;
  let mag: -1 | 0 | 1 = 0;
  if (x.int.length !== y.int.length) mag = x.int.length < y.int.length ? -1 : 1;
  else if (x.int !== y.int) mag = x.int < y.int ? -1 : 1;
  else {
    const len = Math.max(x.frac.length, y.frac.length);
    const fx = x.frac.padEnd(len, "0");
    const fy = y.frac.padEnd(len, "0");
    if (fx !== fy) mag = fx < fy ? -1 : 1;
  }
  return x.neg ? ((-mag || 0) as -1 | 0 | 1) : mag;
}

/**
 * decimal string → 带千分位的展示串。只做字符串操作,不经过 float(金额精度不可丢)。
 * "1234567.50" → "1,234,567.50";"-1200" → "-1,200";非法输入原样返回;null → "—"。
 */
export function formatDecimalString(value: string | number | null | undefined): string {
  // 契约是 decimal string;但未定价行可能是 null,序列化成 number 也不该让整页崩
  if (value == null) return "—";
  if (typeof value !== "string") return String(value);
  const m = /^(-?)(\d+)(\.\d+)?$/.exec(value.trim());
  if (!m) return value;
  const [, sign, intPart, frac = ""] = m;
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${grouped}${frac}`;
}

/** 列表 / 详情的数据源:真实用户走 BFF;demo 账号注入 mock(营销用途),两者走同一套渲染。 */
export interface OrdersSource {
  list(page: number, size: number): Promise<OrdersResult>;
  detail(no: string): Promise<OrderDetailResult>;
}

export const BFF_ORDERS_SOURCE: OrdersSource = { list: getBuyerOrders, detail: getBuyerOrder };
