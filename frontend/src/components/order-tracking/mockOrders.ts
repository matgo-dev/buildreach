/**
 * 订单追踪 Mock 数据 — demo 账号(地推营销)用。
 *
 * 形状与履约门户投影一致(契约 §4.2 v4),走真实用户同一套渲染,六节点按同一套事实点亮。
 * 五单覆盖:已到港 / 双柜(一柜强制离港"报关待补":节点 4 灭 5 亮)/ 部分入仓且部分已装柜(节点 2 灭 3 亮)/
 * 已入仓待装柜 / 已取消。
 */
import type { OrdersSource, PortalOrderDetail, PortalOrderLine, PortalShipment } from "@/lib/api/buyerOrders";

function line(
  sort_order: number,
  name_snapshot: string,
  spec_text_snapshot: string | null,
  unit_code: string,
  unit_label: string,
  qty: string,
  received_qty: string,
  shipped_qty: string,
  unit_price: string,
  line_total: string,
): PortalOrderLine {
  return { name_snapshot, spec_text_snapshot, unit_code, unit_label, qty, received_qty, shipped_qty, unit_price, line_total, sort_order };
}

const NO_CUSTOMS = { customs_status: "NONE", declared_at: null, released_at: null } as const;

function shipment(s: Partial<PortalShipment> & Pick<PortalShipment, "container_no" | "stage">): PortalShipment {
  return {
    container_type: "40HQ",
    vessel_name: null,
    voyage_no: null,
    ...NO_CUSTOMS,
    loaded_at: null,
    etd: null,
    atd: null,
    eta: null,
    port_of_loading: "Ningbo",
    port_of_discharge: "Dar es Salaam",
    milestones: [],
    ...s,
  };
}

const MOCK_ORDERS: PortalOrderDetail[] = [
  // ── 已入仓,待装柜 ──
  {
    no: "SO2026090021",
    created_at: "2026-09-08T03:20:00Z",
    status: "CONFIRMED",
    currency: "USD",
    total_amount: "11600.00",
    stage: "RECEIVED",
    line_count: 2,
    lines: [
      line(1, "Cast Aluminum Entry Door", "1200×2100mm · Bronze", "PCS", "pcs", "80", "80", "0", "85.00", "6800.00"),
      line(2, "Wood Grain Floor Tile 600×600", "Matt · 1.44 m²/box", "SQM", "m²", "800", "800", "0", "6.00", "4800.00"),
    ],
    shipments: [],
  },
  // ── 部分入仓:行 1 已装柜并放行,行 2 仍在备货(节点 2 灭、柜的节点 3–4 亮) ──
  {
    no: "SO2026090015",
    created_at: "2026-09-02T07:45:00Z",
    status: "CONFIRMED",
    currency: "USD",
    total_amount: "11250.00",
    stage: "CONFIRMED",
    line_count: 2,
    lines: [
      line(1, "Steel Rebar HRB400 Φ12", "12m / pc", "M", "m", "5000", "5000", "5000", "0.85", "4250.00"),
      line(2, "Stone Coated Metal Roof Tile", "1340×420mm · Red", "PCS", "pcs", "2000", "1200", "0", "3.50", "7000.00"),
    ],
    shipments: [
      shipment({
        container_no: "MSKU7304512",
        container_type: "20GP",
        stage: "CLEARED",
        vessel_name: "MAERSK KENSINGTON",
        voyage_no: "438S",
        customs_status: "RELEASED",
        declared_at: "2026-09-18",
        released_at: "2026-09-20",
        loaded_at: "2026-09-17T06:30:00Z",
        etd: "2026-09-26",
        eta: "2026-10-24",
      }),
    ],
  },
  // ── 双柜:柜 1 货代先放行单据晚到,强制离港(节点 4 灭 5 亮);柜 2 已放行待离港 ──
  {
    no: "SO2026080042",
    created_at: "2026-08-12T02:10:00Z",
    status: "CONFIRMED",
    currency: "USD",
    total_amount: "18750.00",
    stage: "CLEARED",
    line_count: 3,
    lines: [
      line(1, "Brass Check Valve DN25", null, "PCS", "pcs", "500", "500", "500", "4.20", "2100.00"),
      line(2, "LED Ceiling Fan Light", "48\" · 3 blades", "PCS", "pcs", "300", "300", "300", "18.00", "5400.00"),
      line(3, "Steel Rebar HRB400 Φ16", "12m / pc", "M", "m", "9000", "9000", "9000", "1.25", "11250.00"),
    ],
    shipments: [
      shipment({
        container_no: "COSU6285417",
        stage: "IN_TRANSIT",
        vessel_name: "COSCO SHIPPING ARIES",
        voyage_no: "052W",
        customs_status: "DECLARED",
        declared_at: "2026-09-03",
        loaded_at: "2026-09-02T09:00:00Z",
        etd: "2026-09-05",
        atd: "2026-09-05",
        eta: "2026-10-01",
        milestones: [
          { type: "DEPARTED", event_at: "2026-09-05", location: "Ningbo" },
          { type: "TRANSSHIPMENT", event_at: "2026-09-16", location: "Colombo" },
        ],
      }),
      shipment({
        container_no: "MSCU8374921",
        stage: "CLEARED",
        vessel_name: "MSC ANNA",
        voyage_no: "612E",
        customs_status: "RELEASED",
        declared_at: "2026-09-19",
        released_at: "2026-09-21",
        loaded_at: "2026-09-18T08:15:00Z",
        etd: "2026-09-27",
        eta: "2026-10-22",
      }),
    ],
  },
  // ── 已到港 ──
  {
    no: "SO2026070031",
    created_at: "2026-07-15T01:30:00Z",
    status: "CONFIRMED",
    currency: "USD",
    total_amount: "8850.00",
    stage: "ARRIVED",
    line_count: 3,
    lines: [
      line(1, "Cross Pickaxe Heavy Duty", null, "PCS", "pcs", "500", "500", "500", "6.50", "3250.00"),
      line(2, "Fall Arrester 5m", null, "PCS", "pcs", "200", "200", "200", "12.00", "2400.00"),
      line(3, "Titanium Spring Washer Set M4", null, "SET", "sets", "20000", "20000", "20000", "0.16", "3200.00"),
    ],
    shipments: [
      shipment({
        container_no: "EGLV2059831",
        stage: "ARRIVED",
        vessel_name: "EVER GIVEN",
        voyage_no: "1127-012W",
        customs_status: "RELEASED",
        declared_at: "2026-08-01",
        released_at: "2026-08-03",
        loaded_at: "2026-07-31T05:00:00Z",
        port_of_loading: "Shanghai",
        etd: "2026-08-05",
        atd: "2026-08-05",
        eta: "2026-09-02",
        milestones: [
          { type: "DEPARTED", event_at: "2026-08-05", location: "Shanghai" },
          { type: "ARRIVED", event_at: "2026-09-03", location: "Dar es Salaam" },
        ],
      }),
    ],
  },
  // ── 已取消 ──
  {
    no: "SO2026070012",
    created_at: "2026-07-03T04:00:00Z",
    status: "CANCELLED",
    currency: "USD",
    total_amount: "1200.00",
    stage: "CANCELLED",
    line_count: 1,
    lines: [line(1, "PTFE Seal Gasket DN150", null, "PCS", "pcs", "1000", "0", "0", "1.20", "1200.00")],
    shipments: [],
  },
];

/** demo 数据源:与 BFF 同一接口,列表按下单时间倒序(同履约排序)。 */
export const MOCK_ORDERS_SOURCE: OrdersSource = {
  async list(page, size) {
    const all = [...MOCK_ORDERS].sort((a, b) => b.created_at.localeCompare(a.created_at));
    const items = all.slice((page - 1) * size, page * size).map(({ lines: _l, shipments: _s, ...item }) => item);
    return { kind: "data", page: { items, total: all.length, page, size } };
  },
  async detail(no) {
    const order = MOCK_ORDERS.find((o) => o.no === no);
    if (!order) throw new Error("mock order not found");
    return { kind: "data", order };
  },
};
