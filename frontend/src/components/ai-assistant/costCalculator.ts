/**
 * 成本测算助手 — 到岸/到场成本计算引擎（MOCK）
 *
 * ⚠️ 本文件所有税率、费率、本地价格均为 MOCK 默认值，待业务确认会核定。
 * 纯函数模块：不依赖 React / i18n / I/O，便于单元测试。
 * 计算链见 docs/superpowers/specs/2026-07-02-ai-cost-calculator-design.md。
 */

// ─── 类型 ────────────────────────────────────────
/** 价格基准：出厂价 / 离岸价 / 到岸价 */
export type PriceBasis = "EXW" | "FOB" | "CIF";

/** 品类税率行（坦桑尼亚，MOCK） */
export interface TaxRow {
  id: string;
  /** 参考 HS 编码 */
  hsCode: string;
  /** 进口关税率 */
  dutyPct: number;
  /** 消费税率（多数建材为 0） */
  excisePct: number;
  /** 命中该品类的关键词（zh/en 混合，小写匹配） */
  keywords: string[];
  /**
   * 本地市场零售价相对中国 FOB 单价的倍数（MOCK）。
   * 用于本地采购比价：本地单价 ≈ FOB 单价 × 该倍数。
   */
  localPriceMultiplier: number;
  /** 参考 FOB 单价（USD/件，MOCK）——比价助手在用户不输入价格时使用 */
  refFobUnitPrice: number;
  /** 参考单件体积（CBM，MOCK）——比价助手估算物流时使用 */
  refUnitVolumeCbm: number;
}

export interface CostInput {
  categoryId: string;
  basis: PriceBasis;
  /** 单价（USD/件），按所选基准 */
  unitPrice: number;
  /** 数量（件） */
  quantity: number;
  /** 单件重量（kg） */
  unitWeightKg: number;
  /** 单件体积（CBM） */
  unitVolumeCbm: number;
  /** 目的城市 key（见 LOCAL_TRANSPORT_TABLE） */
  destCity: string;
}

export interface CostLine {
  key: string;
  amount: number;
}

export interface CostBreakdown {
  category: TaxRow;
  totalVolumeCbm: number;
  totalWeightKg: number;
  /** 用户所填基准价对应的货值 = unitPrice × qty */
  goodsValueAtBasis: number;
  /** 中国境内段（EXW→FOB，仅 EXW 基准时 > 0） */
  inlandChina: number;
  fobValue: number;
  freight: number;
  insurance: number;
  cifValue: number;
  duty: number;
  rdl: number;
  excise: number;
  vat: number;
  /** 目的港清关 + 港杂 + 文件 */
  clearance: number;
  /** 本地运输（港→目的城市） */
  localTransport: number;
  landedAtPort: number;
  landedOnSite: number;
  unitCost: number;
  /** 税费明细行（用于渲染） */
  taxLines: CostLine[];
  /** 物流/清关明细行 */
  logisticsLines: CostLine[];
}

export interface ComparisonResult {
  importOnSite: number;
  importUnit: number;
  localUnit: number;
  localTransport: number;
  localOnSite: number;
  /** 本地 − 进口（正数=本地更贵） */
  deltaTotal: number;
  /** delta 相对进口的百分比 */
  deltaPct: number;
  cheaper: "import" | "local";
}

// ─── 费率常量（MOCK / 待核定） ──────────────────────
export const RATES = {
  /** 增值税 VAT */
  vatPct: 0.18,
  /** 铁路发展税 Railway Development Levy */
  rdlPct: 0.015,
  /** 国际海运 USD/CBM（LCL 参考拼柜助手） */
  seaFreightPerCbm: 75,
  /** 保险费率（按 FOB） */
  insurancePct: 0.003,
  /** 起运港杂费 + 文件费（固定/票） */
  originPortDocFee: 280,
  /** 目的港清关代理 + 港杂（固定/票） */
  destClearanceFee: 120,
  /** 中国境内段：内陆运输 + 出口报关（固定/票，仅 EXW 基准计入） */
  inlandChinaFee: 200,
  /** 本地运输默认费率 USD/CBM */
  localTransportDefaultPerCbm: 40,
} as const;

/** 目的城市 → 本地运输费率（USD/CBM，MOCK） */
export const LOCAL_TRANSPORT_TABLE: Record<string, number> = {
  dar: 30, // 达累斯萨拉姆（港口城市）
  zanzibar: 50, // 桑给巴尔
  dodoma: 60, // 多多马
  arusha: 70, // 阿鲁沙
  mwanza: 80, // 姆万扎
};

/** 坦桑尼亚建材品类税率表（MOCK / 待核定，参考 complianceAgent） */
export const TANZANIA_TAX_TABLE: TaxRow[] = [
  { id: "tiles", hsCode: "6907", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.9, refFobUnitPrice: 8, refUnitVolumeCbm: 0.033, keywords: ["瓷砖", "地砖", "墙砖", "抛光砖", "tile", "ceramic"] },
  { id: "steel", hsCode: "7214", dutyPct: 0.10, excisePct: 0, localPriceMultiplier: 1.6, refFobUnitPrice: 6, refUnitVolumeCbm: 0.02, keywords: ["钢材", "螺纹钢", "钢筋", "钢管", "角钢", "steel", "rebar"] },
  { id: "cement", hsCode: "2523", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.5, refFobUnitPrice: 4, refUnitVolumeCbm: 0.03, keywords: ["水泥", "cement"] },
  { id: "pvc_pipe", hsCode: "3917", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.8, refFobUnitPrice: 3, refUnitVolumeCbm: 0.012, keywords: ["pvc", "线管", "水管", "管材", "ppr", "pipe"] },
  { id: "wire", hsCode: "8544", dutyPct: 0.10, excisePct: 0, localPriceMultiplier: 1.7, refFobUnitPrice: 15, refUnitVolumeCbm: 0.008, keywords: ["电线", "电缆", "bv线", "wire", "cable"] },
  { id: "aluminum", hsCode: "7604", dutyPct: 0.10, excisePct: 0, localPriceMultiplier: 1.7, refFobUnitPrice: 12, refUnitVolumeCbm: 0.015, keywords: ["铝型材", "铝合金", "断桥铝", "aluminum", "aluminium"] },
  { id: "door_window", hsCode: "7610", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 2.0, refFobUnitPrice: 45, refUnitVolumeCbm: 0.08, keywords: ["门", "窗", "木门", "钢质门", "推拉窗", "door", "window"] },
  { id: "paint", hsCode: "3209", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.9, refFobUnitPrice: 10, refUnitVolumeCbm: 0.02, keywords: ["涂料", "油漆", "防水", "乳胶漆", "paint", "coating"] },
  { id: "sanitary", hsCode: "6910", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 2.1, refFobUnitPrice: 30, refUnitVolumeCbm: 0.06, keywords: ["卫浴", "洁具", "马桶", "面盆", "sanitary", "toilet"] },
  { id: "hardware", hsCode: "7318", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.8, refFobUnitPrice: 2, refUnitVolumeCbm: 0.003, keywords: ["五金", "螺丝", "螺栓", "紧固件", "膨胀", "hardware", "screw", "bolt"] },
  { id: "tools", hsCode: "8467", dutyPct: 0.10, excisePct: 0, localPriceMultiplier: 1.6, refFobUnitPrice: 25, refUnitVolumeCbm: 0.01, keywords: ["电动工具", "角磨机", "电钻", "电锤", "切割机", "tool", "grinder", "drill"] },
  { id: "other", hsCode: "—", dutyPct: 0.25, excisePct: 0, localPriceMultiplier: 1.8, refFobUnitPrice: 10, refUnitVolumeCbm: 0.03, keywords: [] },
];

/** 默认兜底品类 */
export const DEFAULT_CATEGORY_ID = "other";

// ─── 工具函数 ────────────────────────────────────
/** 四舍五入到分 */
function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function getCategory(categoryId: string): TaxRow {
  return (
    TANZANIA_TAX_TABLE.find((c) => c.id === categoryId) ??
    TANZANIA_TAX_TABLE.find((c) => c.id === DEFAULT_CATEGORY_ID)!
  );
}

/** 按输入文本（产品名/描述/HS）匹配品类，无命中返回 null */
export function detectCategory(text: string): TaxRow | null {
  const lower = text.toLowerCase().trim();
  if (!lower) return null;
  // 先按 HS 编码前缀匹配
  const byHs = TANZANIA_TAX_TABLE.find(
    (c) => c.hsCode !== "—" && lower.startsWith(c.hsCode.slice(0, 4)),
  );
  if (byHs) return byHs;
  // 再按关键词命中数排序
  let best: { row: TaxRow; score: number } | null = null;
  for (const row of TANZANIA_TAX_TABLE) {
    const score = row.keywords.filter((kw) => lower.includes(kw.toLowerCase())).length;
    if (score > 0 && (!best || score > best.score)) best = { row, score };
  }
  return best?.row ?? null;
}

// ─── 核心计算 ────────────────────────────────────
/**
 * 到岸/到场成本测算。
 * EXW → FOB → CIF → 到港 → 到场，逐层加费与计税。
 */
export function calcLandedCost(input: CostInput): CostBreakdown {
  const category = getCategory(input.categoryId);
  const qty = Math.max(0, input.quantity);
  const totalVolumeCbm = round2(qty * input.unitVolumeCbm);
  const totalWeightKg = round2(qty * input.unitWeightKg);
  const goodsValueAtBasis = round2(input.unitPrice * qty);

  const freight = round2(RATES.seaFreightPerCbm * totalVolumeCbm);

  // 依据基准逐层还原到 FOB / CIF
  let inlandChina = 0;
  let fobValue: number;
  let insurance: number;
  let cifValue: number;

  if (input.basis === "EXW") {
    inlandChina = RATES.inlandChinaFee + RATES.originPortDocFee;
    fobValue = round2(goodsValueAtBasis + inlandChina);
    insurance = round2(fobValue * RATES.insurancePct);
    cifValue = round2(fobValue + freight + insurance);
  } else if (input.basis === "FOB") {
    fobValue = goodsValueAtBasis;
    insurance = round2(fobValue * RATES.insurancePct);
    cifValue = round2(fobValue + freight + insurance);
  } else {
    // CIF：用户给的即完税价，海运与保险已含
    cifValue = goodsValueAtBasis;
    insurance = round2((cifValue / (1 + RATES.insurancePct)) * RATES.insurancePct);
    fobValue = round2(cifValue - freight - insurance);
  }

  // 税费（以 CIF 为完税价）
  const duty = round2(cifValue * category.dutyPct);
  const rdl = round2(cifValue * RATES.rdlPct);
  const excise = round2(cifValue * category.excisePct);
  const vat = round2((cifValue + duty + rdl + excise) * RATES.vatPct);

  const clearance = RATES.destClearanceFee;

  const perCbm = LOCAL_TRANSPORT_TABLE[input.destCity] ?? RATES.localTransportDefaultPerCbm;
  const localTransport = round2(perCbm * totalVolumeCbm);

  const landedAtPort = round2(cifValue + duty + rdl + excise + vat + clearance);
  const landedOnSite = round2(landedAtPort + localTransport);
  const unitCost = qty > 0 ? round2(landedOnSite / qty) : 0;

  const taxLines: CostLine[] = [
    { key: "duty", amount: duty },
    { key: "rdl", amount: rdl },
    { key: "excise", amount: excise },
    { key: "vat", amount: vat },
  ];
  const logisticsLines: CostLine[] = [
    { key: "freight", amount: freight },
    { key: "insurance", amount: insurance },
    { key: "clearance", amount: clearance },
    { key: "localTransport", amount: localTransport },
  ];
  if (inlandChina > 0) logisticsLines.unshift({ key: "inlandChina", amount: inlandChina });

  return {
    category,
    totalVolumeCbm,
    totalWeightKg,
    goodsValueAtBasis,
    inlandChina,
    fobValue,
    freight,
    insurance,
    cifValue,
    duty,
    rdl,
    excise,
    vat,
    clearance,
    localTransport,
    landedAtPort,
    landedOnSite,
    unitCost,
    taxLines,
    logisticsLines,
  };
}

/**
 * 本地采购 vs 进口采购 到场成本对比（MOCK）。
 * 本地单价 ≈ FOB 单价 × 品类倍数；本地运输沿用目的城市费率。
 */
export function compareLocalVsImport(input: CostInput, breakdown: CostBreakdown): ComparisonResult {
  const qty = Math.max(0, input.quantity);
  // FOB 单价：EXW/CIF 基准时按 breakdown 反推
  const fobUnit = qty > 0 ? breakdown.fobValue / qty : 0;
  const localUnit = round2(fobUnit * breakdown.category.localPriceMultiplier);
  const perCbm = LOCAL_TRANSPORT_TABLE[input.destCity] ?? RATES.localTransportDefaultPerCbm;
  const localTransport = round2(perCbm * breakdown.totalVolumeCbm);
  const localOnSite = round2(localUnit * qty + localTransport);

  const importOnSite = breakdown.landedOnSite;
  const importUnit = breakdown.unitCost;
  const deltaTotal = round2(localOnSite - importOnSite);
  const deltaPct = importOnSite > 0 ? round2((deltaTotal / importOnSite) * 100) : 0;

  return {
    importOnSite,
    importUnit,
    localUnit,
    localTransport,
    localOnSite,
    deltaTotal,
    deltaPct,
    cheaper: deltaTotal >= 0 ? "import" : "local",
  };
}
