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
      { name: "不锈钢铰链 4寸", nameEn: "Stainless Steel Hinge 4\"", sku: "HDW-HNG-SS4", qty: 2000, unit: "pcs", unitPrice: 0.85, currency: "USD", image: "https://picsum.photos/seed/hinge/80/80", supplier: "浙江恒盛五金" },
      { name: "碳钢螺栓 M12×80", nameEn: "Carbon Steel Bolt M12×80", sku: "FST-BLT-M12", qty: 5000, unit: "pcs", unitPrice: 0.12, currency: "USD", image: "https://picsum.photos/seed/bolt/80/80", supplier: "温州标准件厂" },
      { name: "PPR 给水管 20mm", nameEn: "PPR Water Pipe 20mm", sku: "PIP-PPR-20", qty: 3000, unit: "m", unitPrice: 1.20, currency: "USD", image: "https://picsum.photos/seed/pipe/80/80", supplier: "浙江伟星管业" },
      { name: "LED 面板灯 600×600", nameEn: "LED Panel Light 600×600", sku: "ELC-LED-P60", qty: 500, unit: "pcs", unitPrice: 12.50, currency: "USD", image: "https://picsum.photos/seed/ledpanel/80/80", supplier: "中山欧普照明" },
      { name: "防水涂料 20kg", nameEn: "Waterproof Coating 20kg", sku: "CHM-WPC-20", qty: 200, unit: "barrel", unitPrice: 15.00, currency: "USD", image: "https://picsum.photos/seed/coating/80/80", supplier: "广州雨虹防水" },
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
      { name: "镀锌方管 40×40×2.0", nameEn: "Galvanized Square Tube 40×40", sku: "STL-GST-40", qty: 800, unit: "pcs", unitPrice: 8.50, currency: "USD", image: "https://picsum.photos/seed/steeltube/80/80", supplier: "天津友联钢管" },
      { name: "水泥 42.5R", nameEn: "Portland Cement 42.5R", sku: "BLD-CMT-425", qty: 1000, unit: "bag", unitPrice: 4.80, currency: "USD", image: "https://picsum.photos/seed/cement/80/80", supplier: "海螺水泥" },
      { name: "瓷砖 800×800", nameEn: "Porcelain Tile 800×800", sku: "TIL-PCT-800", qty: 2000, unit: "sqm", unitPrice: 6.00, currency: "USD", image: "https://picsum.photos/seed/tile/80/80", supplier: "佛山东鹏陶瓷" },
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
      { name: "安全帽 ABS", nameEn: "ABS Safety Helmet", sku: "SAF-HLM-ABS", qty: 1000, unit: "pcs", unitPrice: 2.80, currency: "USD", image: "https://picsum.photos/seed/helmet/80/80", supplier: "苏州赛邦防护" },
      { name: "劳保手套 丁腈", nameEn: "Nitrile Work Gloves", sku: "SAF-GLV-NTR", qty: 5000, unit: "pairs", unitPrice: 0.45, currency: "USD", image: "https://picsum.photos/seed/gloves/80/80", supplier: "山东星宇手套" },
      { name: "电动角磨机 125mm", nameEn: "Angle Grinder 125mm", sku: "TLS-AGR-125", qty: 200, unit: "pcs", unitPrice: 18.50, currency: "USD", image: "https://picsum.photos/seed/grinder/80/80", supplier: "江苏东成电动" },
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
