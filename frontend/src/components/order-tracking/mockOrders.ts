/**
 * 订单追踪 Mock 数据 — 地推 demo 用
 *
 * 模拟 3 笔订单：海运在途 / 已到港清关 / 已交付
 */

export type MilestoneStatus = "done" | "current" | "upcoming";

export interface Milestone {
  id: string;
  labelKey: string;           // i18n key
  status: MilestoneStatus;
  date?: string;              // ISO date or null
  detail?: string;            // 额外说明
  docs?: { name: string; type: string }[];  // 关联单据
}

export interface Shipment {
  id: string;
  label: string;              // "包裹 1" / "Package 1"
  carrier: string;
  trackingNo: string;
  containerType: string;      // "20GP" / "40HQ"
  milestones: Milestone[];
}

export interface OrderItem {
  name: string;
  nameEn: string;
  sku: string;
  qty: number;
  unit: string;
  unitPrice: number;
  currency: string;
  image: string;
  supplier: string;
}

export interface MockOrder {
  id: string;
  orderNo: string;
  statusKey: string;          // i18n key for status badge
  statusColor: string;        // tailwind color class
  createdAt: string;
  totalAmount: number;
  currency: string;
  eta: string;
  buyerCompany: string;
  currentMilestoneKey: string; // 当前节点 i18n key
  progress: number;           // 0-100 进度百分比
  shipments: Shipment[];
  items: OrderItem[];
  documents: { name: string; type: string; date: string }[];
}

// 统一的履约节点定义（中国→东非建材供应链）
export const MILESTONE_KEYS = [
  "msOrderConfirmed",      // 订单确认
  "msSupplierPrep",        // 供应商备货
  "msQualityInspection",   // 质检验货
  "msWarehouseReceipt",    // 入仓集货
  "msConsolidation",       // 拼柜装箱
  "msCustomsExport",       // 出口报关
  "msSeaFreight",          // 海运在途
  "msPortArrival",         // 到达目的港
  "msCustomsImport",       // 目的港清关
  "msLocalDelivery",       // 本地配送
  "msDelivered",           // 签收确认
] as const;

function buildMilestones(
  currentIndex: number,
  dates: (string | undefined)[],
): Milestone[] {
  return MILESTONE_KEYS.map((key, i) => ({
    id: `ms-${i}`,
    labelKey: key,
    status: i < currentIndex ? "done" : i === currentIndex ? "current" : "upcoming",
    date: dates[i],
  }));
}

export const MOCK_ORDERS: MockOrder[] = [
  // ── 订单 1：海运在途 ──
  {
    id: "1",
    orderNo: "BL-2026-00158",
    statusKey: "statusInTransit",
    statusColor: "bg-blue-100 text-blue-700 border-blue-200",
    createdAt: "2026-05-20",
    totalAmount: 18_750.00,
    currency: "USD",
    eta: "2026-07-15",
    buyerCompany: "Mkombozi Hardware Ltd.",
    currentMilestoneKey: "msSeaFreight",
    progress: 60,
    shipments: [
      {
        id: "s1",
        label: "Shipment 1",
        carrier: "COSCO Shipping",
        trackingNo: "COSU6285417",
        containerType: "20GP",
        milestones: buildMilestones(6, [
          "2026-05-20", "2026-05-22", "2026-05-28", "2026-06-01",
          "2026-06-05", "2026-06-08", "2026-06-10",
          undefined, undefined, undefined, undefined,
        ]),
      },
      {
        id: "s2",
        label: "Shipment 2",
        carrier: "MSC",
        trackingNo: "MSCU8374921",
        containerType: "20GP",
        milestones: buildMilestones(5, [
          "2026-05-20", "2026-05-25", "2026-05-30", "2026-06-03",
          "2026-06-07", "2026-06-12",
          undefined, undefined, undefined, undefined, undefined,
        ]),
      },
    ],
    items: [
      { name: "彩石金属瓦", nameEn: "Stone Coated Metal Roof Tile", sku: "ROF-SCM-01", qty: 2000, unit: "pcs", unitPrice: 3.50, currency: "USD", image: "/images/mock/roof-tile.jpg", supplier: "杭州优铸建材" },
      { name: "螺纹钢筋 HRB400 Φ12", nameEn: "Steel Rebar HRB400 Φ12", sku: "STL-RBR-12", qty: 5000, unit: "m", unitPrice: 0.85, currency: "USD", image: "/images/mock/steel-rebar.jpg", supplier: "唐山建龙钢铁" },
      { name: "黄铜止回阀 DN25", nameEn: "Brass Check Valve DN25", sku: "PLB-BCV-25", qty: 500, unit: "pcs", unitPrice: 4.20, currency: "USD", image: "/images/mock/brass-valve.jpg", supplier: "玉环阀门厂" },
      { name: "LED 风扇吸顶灯", nameEn: "LED Ceiling Fan Light", sku: "ELC-CFL-01", qty: 300, unit: "pcs", unitPrice: 18.00, currency: "USD", image: "/images/mock/led-ceiling-light.jpg", supplier: "中山欧普照明" },
      { name: "PTFE 密封垫片 DN150", nameEn: "PTFE Seal Gasket DN150", sku: "FST-GSK-150", qty: 1000, unit: "pcs", unitPrice: 1.20, currency: "USD", image: "/images/mock/seal-gasket.png", supplier: "温州密封件厂" },
    ],
    documents: [
      { name: "Proforma Invoice", type: "PI", date: "2026-05-20" },
      { name: "Packing List", type: "PL", date: "2026-06-05" },
      { name: "Bill of Lading (S1)", type: "B/L", date: "2026-06-10" },
      { name: "Certificate of Origin", type: "CO", date: "2026-06-08" },
      { name: "Quality Inspection Report", type: "QC", date: "2026-05-28" },
    ],
  },

  // ── 订单 2：到港清关中 ──
  {
    id: "2",
    orderNo: "BL-2026-00142",
    statusKey: "statusCustomsClearance",
    statusColor: "bg-amber-100 text-amber-700 border-amber-200",
    createdAt: "2026-04-28",
    totalAmount: 32_400.00,
    currency: "USD",
    eta: "2026-06-28",
    buyerCompany: "Dar Building Solutions Co.",
    currentMilestoneKey: "msCustomsImport",
    progress: 82,
    shipments: [
      {
        id: "s3",
        label: "Shipment 1",
        carrier: "Evergreen",
        trackingNo: "EGLV2059831",
        containerType: "40HQ",
        milestones: buildMilestones(8, [
          "2026-04-28", "2026-05-02", "2026-05-08", "2026-05-12",
          "2026-05-15", "2026-05-18", "2026-05-20", "2026-06-18",
          "2026-06-20", undefined, undefined,
        ]),
      },
    ],
    items: [
      { name: "铸铝入户门", nameEn: "Cast Aluminum Entry Door", sku: "DOR-CAD-01", qty: 200, unit: "pcs", unitPrice: 85.00, currency: "USD", image: "/images/mock/entry-door.jpg", supplier: "佛山万嘉门业" },
      { name: "木纹地板砖 600×600", nameEn: "Wood Grain Floor Tile 600×600", sku: "TIL-WGF-60", qty: 3000, unit: "sqm", unitPrice: 5.80, currency: "USD", image: "/images/mock/floor-tile.jpg", supplier: "佛山东鹏陶瓷" },
      { name: "乔立垫片 M12", nameEn: "Flat Washer M12", sku: "FST-WSH-M12", qty: 10000, unit: "pcs", unitPrice: 0.03, currency: "USD", image: "/images/mock/washer.jpg", supplier: "温州标准件厂" },
    ],
    documents: [
      { name: "Proforma Invoice", type: "PI", date: "2026-04-28" },
      { name: "Commercial Invoice", type: "CI", date: "2026-05-18" },
      { name: "Packing List", type: "PL", date: "2026-05-15" },
      { name: "Bill of Lading", type: "B/L", date: "2026-05-20" },
      { name: "Certificate of Origin", type: "CO", date: "2026-05-18" },
      { name: "Quality Inspection Report", type: "QC", date: "2026-05-08" },
      { name: "Fumigation Certificate", type: "FC", date: "2026-05-15" },
    ],
  },

  // ── 订单 3：已交付 ──
  {
    id: "3",
    orderNo: "BL-2026-00119",
    statusKey: "statusDelivered",
    statusColor: "bg-green-100 text-green-700 border-green-200",
    createdAt: "2026-03-15",
    totalAmount: 9_800.00,
    currency: "USD",
    eta: "2026-05-20",
    buyerCompany: "Kariakoo Supplies Tanzania",
    currentMilestoneKey: "msDelivered",
    progress: 100,
    shipments: [
      {
        id: "s4",
        label: "Shipment 1",
        carrier: "COSCO Shipping",
        trackingNo: "COSU5193748",
        containerType: "20GP",
        milestones: buildMilestones(11, [
          "2026-03-15", "2026-03-18", "2026-03-22", "2026-03-25",
          "2026-03-28", "2026-03-30", "2026-04-02", "2026-04-28",
          "2026-05-02", "2026-05-10", "2026-05-15",
        ]),
      },
    ],
    items: [
      { name: "十字镐 双扁大号", nameEn: "Cross Pickaxe Heavy Duty", sku: "TLS-PKX-01", qty: 500, unit: "pcs", unitPrice: 6.50, currency: "USD", image: "/images/mock/pickaxe.jpg", supplier: "河北富乐皇工具" },
      { name: "防坠器 5米", nameEn: "Fall Arrester 5m", sku: "SAF-FAR-05", qty: 200, unit: "pcs", unitPrice: 12.00, currency: "USD", image: "/images/mock/fall-arrester.png", supplier: "京固安防" },
      { name: "钛合金平弹垫组合 M4", nameEn: "Titanium Spring Washer Set M4", sku: "FST-TWS-M4", qty: 5000, unit: "pcs", unitPrice: 0.15, currency: "USD", image: "/images/mock/titanium-washer.png", supplier: "固万基紧固件" },
    ],
    documents: [
      { name: "Proforma Invoice", type: "PI", date: "2026-03-15" },
      { name: "Packing List", type: "PL", date: "2026-03-28" },
      { name: "Bill of Lading", type: "B/L", date: "2026-04-02" },
      { name: "Certificate of Origin", type: "CO", date: "2026-03-30" },
      { name: "Delivery Receipt", type: "DR", date: "2026-05-15" },
    ],
  },
];
