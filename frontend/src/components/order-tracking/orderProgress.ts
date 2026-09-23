// 六节点进度的纯派生(契约 docs/specs/2026-09-21-0214 §4.3 / §5.3,v4.1)。
// 两条口径各管各的,不互相推:
//   - 逐节点点亮只认事实:订单级事实点亮 1–2,柜级事实逐柜点亮 3–6,不按 stage 序号反推前序节点。
//     部分发货会出现 2 灭 3 亮、强制通道离港会出现 4 灭 5 亮——都是"还差什么"的如实显示,不补亮。
//   - 进度百分比与路线图当前位置由订单 stage 驱动(列表卡上唯一的标量)。
import {
  compareDecimalStrings,
  type OrderStage,
  type PortalOrderDetail,
  type PortalShipment,
  type ShipmentStage,
} from "@/lib/api/buyerOrders";

/** 六个节点(顺序即展示顺序);标签 key 在 messages/orderTracking。hero 的节点数也取自这里。 */
export const FULFILLMENT_NODES = [
  "msOrderConfirmed",   // 1 订单确认   订单 status = CONFIRMED
  "msWarehouseReceipt", // 2 入仓集货   全部行 received_qty ≥ qty
  "msConsolidation",    // 3 拼柜装箱   柜 stage ≥ LOADED
  "msCustomsExport",    // 4 出口报关   柜 customs_status = RELEASED
  "msSeaFreight",       // 5 海运在途   柜 atd 非空
  "msPortArrival",      // 6 到达目的港 柜有 ARRIVED 里程碑
] as const;

export type NodeKey = (typeof FULFILLMENT_NODES)[number];

/** 柜级递进链上的已知值。柜投影只含已装柜的柜,链上任一值即"≥ LOADED";不认识的值不算。 */
const SHIPMENT_CHAIN: Record<ShipmentStage, true> = { LOADED: true, CLEARED: true, IN_TRANSIT: true, ARRIVED: true };

/** 一行已备齐:received_qty ≥ qty(decimal 字符串比较;非法值按未备齐)。 */
export function lineFullyReceived(line: { qty: string; received_qty: string }): boolean {
  const c = compareDecimalStrings(line.received_qty, line.qty);
  return c !== null && c >= 0;
}

/** 已备齐的行数(节点 2 的说明文字用)。 */
export function countReceivedLines(lines: readonly { qty: string; received_qty: string }[]): number {
  return lines.filter(lineFullyReceived).length;
}

/**
 * 某订单(可选某柜)下六个节点各自是否点亮。shipment 为 null(尚无柜)时 3–6 全灭。
 * 返回值下标与 FULFILLMENT_NODES 一一对应。
 */
export function litNodes(
  order: Pick<PortalOrderDetail, "status" | "lines">,
  shipment: PortalShipment | null,
): boolean[] {
  const confirmed = order.status === "CONFIRMED";
  // 空行单不能因"全部满足"的空真而点亮
  const received = order.lines.length > 0 && order.lines.every(lineFullyReceived);
  if (!shipment) return [confirmed, received, false, false, false, false];
  return [
    confirmed,
    received,
    SHIPMENT_CHAIN[shipment.stage as ShipmentStage] === true,
    shipment.customs_status === "RELEASED",
    shipment.atd != null && shipment.atd !== "",
    shipment.milestones.some((m) => m.type === "ARRIVED"),
  ];
}

/** 只认表的自有属性:履约新增而前端不认识的 key(或 "constructor" 这类原型链名)→ null。 */
export function lookup<K extends string, V>(table: Record<K, V>, key: string): V | null {
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key as K] : null;
}

/** 订单 stage → 展示位置(单一源头):进度百分比(六档均分)与路线图当前位置下标。
 *  路线图到港即全程完成,下标越过末节点(5 个节点,下标 5 = 全部完成)。CANCELLED 不画,故不在表内。 */
export const STAGE_VIEW: Record<Exclude<OrderStage, "CANCELLED">, { progress: number; routeIndex: number }> = {
  CONFIRMED: { progress: 0, routeIndex: 0 },    // 备货中:货在工厂
  RECEIVED: { progress: 20, routeIndex: 1 },    // 已入仓:集货仓
  LOADED: { progress: 40, routeIndex: 2 },      // 已装柜:出发港
  CLEARED: { progress: 60, routeIndex: 2 },     // 已放行:仍在出发港
  IN_TRANSIT: { progress: 80, routeIndex: 3 },  // 海运
  ARRIVED: { progress: 100, routeIndex: 5 },    // 已到 Dar es Salaam:全部完成
};

/** 取进度百分比;CANCELLED 或履约新增而前端不认识的 stage → null(不画进度条,不冒充已知阶段)。 */
export function stageProgress(stage: string): number | null {
  return lookup(STAGE_VIEW, stage)?.progress ?? null;
}

/** 路线图当前位置下标;CANCELLED 或不认识的 stage → null(不定位)。 */
export function stageRouteIndex(stage: string): number | null {
  return lookup(STAGE_VIEW, stage)?.routeIndex ?? null;
}
