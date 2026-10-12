// 六节点进度与分段占比的纯派生(契约 docs/specs/2026-09-21-0214 §4.3 / §5.3,v5)。
// 三条口径各管各的,不互相推:
//   - 阶段徽标由订单 stage 驱动(履约整单事实六态);
//   - 分段进度条由 value_segments 驱动(履约按货值切好的五段,这里只算占比);
//   - 逐节点点亮只认事实:订单级事实点亮 1(–2),柜级事实逐柜点亮 2–6,不按 stage 序号反推。
//     强制通道离港会出现 4 灭 5 亮——"还差什么"的如实显示,不补亮。
// 单测:orderProgress.test.ts。
import {
  compareDecimalStrings,
  type PortalOrderDetail,
  type PortalOrderLine,
  type PortalShipment,
  type PortalValueSegments,
  type ShipmentStage,
} from "@/lib/api/buyerOrders";

/** 六个节点(顺序即展示顺序);标签 key 在 messages/orderTracking。hero 的节点数也取自这里。 */
export const FULFILLMENT_NODES = [
  "msOrderConfirmed",   // 1 订单确认   订单 status = CONFIRMED
  "msWarehouseReceipt", // 2 入仓集货   有柜:本柜已装柜(装进柜的货必然入过仓);无柜:全部行 received_qty ≥ qty
  "msConsolidation",    // 3 拼柜装箱   柜 stage ≥ LOADED
  "msCustomsExport",    // 4 出口报关   柜 customs_status = RELEASED
  "msSeaFreight",       // 5 海运在途   柜 atd 非空
  "msPortArrival",      // 6 到达目的港 柜有 ARRIVED 里程碑
] as const;

export type NodeKey = (typeof FULFILLMENT_NODES)[number];

/** 柜级递进链上的已知值。柜投影只含已装柜的柜,链上任一值即"≥ LOADED";不认识的值不算。 */
const SHIPMENT_CHAIN: Record<ShipmentStage, true> = { LOADED: true, CLEARED: true, IN_TRANSIT: true, ARRIVED: true };

/** a ≥ b(decimal 字符串比较;任一非法 → false,按"事实未成立")。 */
function gte(a: string, b: string): boolean {
  const c = compareDecimalStrings(a, b);
  return c !== null && c >= 0;
}

/** 一行已备齐:received_qty ≥ qty。 */
export function lineFullyReceived(line: { qty: string; received_qty: string }): boolean {
  return gte(line.received_qty, line.qty);
}

/** 已备齐的行数(节点 2 的订单级副文案用)。 */
export function countReceivedLines(lines: readonly { qty: string; received_qty: string }[]): number {
  return lines.filter(lineFullyReceived).length;
}

/** 还有待装柜量的行(「待装柜」tab 的行集),按 sort_order 排。pending_qty 缺失 / 非法 → 不算待装。 */
export function pendingLines(lines: readonly PortalOrderLine[]): PortalOrderLine[] {
  return lines
    .filter((l) => {
      const c = compareDecimalStrings(l.pending_qty, "0");
      return c !== null && c > 0;
    })
    .sort((a, b) => a.sort_order - b.sort_order);
}

/** 待装的货已全部在仓:in_warehouse_qty ≥ pending_qty。 */
export function lineInWarehouse(line: { pending_qty: string; in_warehouse_qty: string }): boolean {
  return gte(line.in_warehouse_qty, line.pending_qty);
}

/**
 * 某订单(可选某柜)下六个节点各自是否点亮。shipment 为 null(待装柜 / 尚无柜)时 3–6 全灭。
 * 返回值下标与 FULFILLMENT_NODES 一一对应。
 */
export function litNodes(
  order: Pick<PortalOrderDetail, "status" | "lines">,
  shipment: PortalShipment | null,
): boolean[] {
  const confirmed = order.status === "CONFIRMED";
  if (!shipment) {
    // 空行单不能因"全部满足"的空真而点亮
    const received = order.lines.length > 0 && order.lines.every(lineFullyReceived);
    return [confirmed, received, false, false, false, false];
  }
  const loaded = SHIPMENT_CHAIN[shipment.stage as ShipmentStage] === true;
  return [
    confirmed,
    // 柜视图按本柜:装进柜的货必然先入过仓,这是本柜事实不是推断(契约 §5.3 v5)
    loaded,
    loaded,
    shipment.customs_status === "RELEASED",
    shipment.atd != null && shipment.atd !== "",
    shipment.milestones.some((m) => m.type === "ARRIVED"),
  ];
}

/** 只认表的自有属性:履约新增而前端不认识的 key(或 "constructor" 这类原型链名)→ null。 */
export function lookup<K extends string, V>(table: Record<K, V>, key: string): V | null {
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key as K] : null;
}

/** 五段展示顺序(最领先在前),与履约 value_segments 的键一一对应;标签 key = `seg` + 大驼峰。 */
export const SEGMENT_KEYS = ["arrived", "in_transit", "loaded", "in_warehouse", "not_received"] as const;
export type SegmentKey = (typeof SEGMENT_KEYS)[number];

/**
 * 分段条占比:每段 ÷ 五段之和。**这里允许 Number()**——它只决定条宽与百分号文字,不是金额显示,
 * 不进任何比较或求和(契约 §5.3 v5);非法 / 缺失按 0,和为 0 时全 0 而不是 NaN。
 */
export function segmentShares(segments: PortalValueSegments): { key: SegmentKey; share: number }[] {
  const amounts = SEGMENT_KEYS.map((key) => {
    const n = Number(segments[key]);
    return Number.isFinite(n) && n > 0 ? n : 0;
  });
  const total = amounts.reduce((a, b) => a + b, 0);
  return SEGMENT_KEYS.map((key, i) => ({ key, share: total > 0 ? amounts[i] / total : 0 }));
}
