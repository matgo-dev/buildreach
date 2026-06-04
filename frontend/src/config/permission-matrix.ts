/**
 * 单一可信源(v3 §5):整个前端的权限相关展示 / 校验 / 过滤都从这里读。
 *
 * 与后端 app/rbac/scope_config.py + permissions_config.py 等价。
 * 后端是权威,前端是 UX 友好层 — 任何冲突以后端为准。
 */

import type { RoleCode } from "@/lib/auth";

// ---------- 权限点(v3 §3,32 个业务 + 3 个 auth 底层)----------

export const Permissions = {
  // auth 底层
  AUTH_LOGIN: "auth:login",
  AUTH_LOGOUT: "auth:logout",
  AUTH_ME: "auth:me",

  SUPPLIER_READ: "supplier:read",
  SUPPLIER_WRITE: "supplier:write",
  SUPPLIER_APPROVE: "supplier:approve",
  SUPPLIER_REJECT: "supplier:reject",

  PRODUCT_READ: "product:read",
  PRODUCT_WRITE: "product:write",
  PRODUCT_APPROVE: "product:approve",
  PRODUCT_REJECT: "product:reject",

  COUNTRY_READ: "country:read",
  COUNTRY_WRITE: "country:write",

  CREDIT_READ: "credit:read",
  CREDIT_WRITE: "credit:write",
  CREDIT_RECOMPUTE: "credit:recompute",

  PROJECT_READ: "project:read",
  PROJECT_WRITE: "project:write",

  PURCHASE_LIST_READ: "purchase_list:read",
  PURCHASE_LIST_WRITE: "purchase_list:write",

  CART_READ: "cart:read",
  CART_WRITE: "cart:write",

  RFQ_READ: "rfq:read",
  RFQ_CREATE: "rfq:create",
  RFQ_RESPOND: "rfq:respond",

  QUOTE_READ: "quote:read",
  QUOTE_WRITE: "quote:write",

  ORDER_READ: "order:read",
  ORDER_WRITE: "order:write",
  ORDER_CHECKIN: "order:checkin",

  MEMBERSHIP_READ: "membership:read",
  MEMBERSHIP_WRITE: "membership:write",

  RISK_READ: "risk:read",

  USER_MANAGE: "user:manage",
  ROLE_MANAGE: "role:manage",
  PERMISSION_MANAGE: "permission:manage",
  SYSTEM_CONFIG: "system:config",
  SYSTEM_AUDIT: "system:audit",
} as const;

export type PermissionCode = (typeof Permissions)[keyof typeof Permissions];

// ---------- 资源域(v3 §2 + 信用评估 §六,16 个)----------

export type ResourceCode =
  | "supplier" | "product" | "country" | "credit"
  | "project" | "purchase_list" | "cart" | "rfq" | "quote" | "order"
  | "membership" | "risk"
  | "user" | "role" | "permission" | "system";

export const RESOURCES: Record<ResourceCode, { code: ResourceCode; name: string; module: string }> = {
  supplier:      { code: "supplier",      name: "供应商档案", module: "业务-档案" },
  product:       { code: "product",       name: "商品 SKU",   module: "业务-档案" },
  country:       { code: "country",       name: "国别准入",   module: "业务-档案" },
  credit:        { code: "credit",        name: "信用评估",   module: "业务-档案" },
  project:       { code: "project",       name: "项目",       module: "业务-交易" },
  purchase_list: { code: "purchase_list", name: "采购清单",   module: "业务-交易" },
  cart:          { code: "cart",          name: "购物车",     module: "业务-交易" },
  rfq:           { code: "rfq",           name: "询价单",     module: "业务-交易" },
  quote:         { code: "quote",         name: "报价",       module: "业务-交易" },
  order:         { code: "order",         name: "订单",       module: "业务-交易" },
  membership:    { code: "membership",    name: "会员",       module: "业务-供应商" },
  risk:          { code: "risk",          name: "风控驾驶舱", module: "业务-运营" },
  user:          { code: "user",          name: "用户管理",   module: "系统" },
  role:          { code: "role",          name: "角色管理",   module: "系统" },
  permission:    { code: "permission",    name: "权限管理",   module: "系统" },
  system:        { code: "system",        name: "系统配置",   module: "系统" },
};

// ---------- 角色 × 资源 → scope(v3 §4 权威表)----------

export type Scope = "ALL" | "ORG" | "OWN" | "NONE";

export const ROLE_RESOURCE_SCOPE: Record<RoleCode, Record<ResourceCode, Scope>> = {
  BUYER: {
    supplier: "ALL", product: "ALL", country: "ALL", credit: "ALL",
    project: "ORG", purchase_list: "ORG", cart: "OWN",
    rfq: "ORG", quote: "ORG", order: "ORG",
    membership: "NONE", risk: "NONE",
    user: "NONE", role: "NONE", permission: "NONE", system: "NONE",
  },
  SUPPLIER: {
    supplier: "OWN", product: "OWN", country: "ALL", credit: "NONE",
    project: "NONE", purchase_list: "NONE", cart: "NONE",
    rfq: "OWN", quote: "OWN", order: "OWN",
    membership: "OWN", risk: "NONE",
    user: "NONE", role: "NONE", permission: "NONE", system: "NONE",
  },
  OPERATOR: {
    supplier: "ALL", product: "ALL", country: "ALL", credit: "ALL",
    project: "ALL", purchase_list: "ALL", cart: "NONE",
    rfq: "ALL", quote: "ALL", order: "ALL",
    membership: "ALL", risk: "ALL",
    user: "NONE", role: "NONE", permission: "NONE", system: "NONE",
  },
  ADMIN: {
    supplier: "NONE", product: "NONE", country: "NONE", credit: "NONE",
    project: "NONE", purchase_list: "NONE", cart: "NONE",
    rfq: "NONE", quote: "NONE", order: "NONE",
    membership: "NONE", risk: "NONE",
    user: "ALL", role: "ALL", permission: "ALL", system: "ALL",
  },
};

// ---------- 角色 × 资源 → 持有的权限点列表(v3 §3 权威表)----------

export const ROLE_RESOURCE_PERMISSIONS: Record<
  RoleCode,
  Partial<Record<ResourceCode, PermissionCode[]>>
> = {
  BUYER: {
    supplier: [Permissions.SUPPLIER_READ],
    product: [Permissions.PRODUCT_READ],
    country: [Permissions.COUNTRY_READ],
    credit: [Permissions.CREDIT_READ],
    project: [Permissions.PROJECT_READ, Permissions.PROJECT_WRITE],
    purchase_list: [Permissions.PURCHASE_LIST_READ, Permissions.PURCHASE_LIST_WRITE],
    cart: [Permissions.CART_READ, Permissions.CART_WRITE],
    rfq: [Permissions.RFQ_READ, Permissions.RFQ_CREATE],
    quote: [Permissions.QUOTE_READ],
    order: [Permissions.ORDER_READ, Permissions.ORDER_WRITE],
  },
  SUPPLIER: {
    supplier: [Permissions.SUPPLIER_READ, Permissions.SUPPLIER_WRITE],
    product: [Permissions.PRODUCT_READ, Permissions.PRODUCT_WRITE],
    country: [Permissions.COUNTRY_READ],
    rfq: [Permissions.RFQ_READ, Permissions.RFQ_RESPOND],
    quote: [Permissions.QUOTE_READ, Permissions.QUOTE_WRITE],
    order: [Permissions.ORDER_READ, Permissions.ORDER_WRITE, Permissions.ORDER_CHECKIN],
    membership: [Permissions.MEMBERSHIP_READ, Permissions.MEMBERSHIP_WRITE],
  },
  OPERATOR: {
    supplier: [Permissions.SUPPLIER_READ, Permissions.SUPPLIER_APPROVE, Permissions.SUPPLIER_REJECT],
    product: [Permissions.PRODUCT_READ, Permissions.PRODUCT_APPROVE, Permissions.PRODUCT_REJECT],
    country: [Permissions.COUNTRY_READ, Permissions.COUNTRY_WRITE],
    credit: [Permissions.CREDIT_READ, Permissions.CREDIT_WRITE, Permissions.CREDIT_RECOMPUTE],
    project: [Permissions.PROJECT_READ],
    purchase_list: [Permissions.PURCHASE_LIST_READ],
    rfq: [Permissions.RFQ_READ],
    quote: [Permissions.QUOTE_READ],
    order: [Permissions.ORDER_READ],
    membership: [Permissions.MEMBERSHIP_READ],
    risk: [Permissions.RISK_READ],
  },
  ADMIN: {
    user: [Permissions.USER_MANAGE],
    role: [Permissions.ROLE_MANAGE],
    permission: [Permissions.PERMISSION_MANAGE],
    system: [Permissions.SYSTEM_CONFIG, Permissions.SYSTEM_AUDIT],
  },
};

// ---------- 矩阵符号:全/读/己/管/无(v3 §7.2 + 用户矩阵图)----------

export type MatrixSymbol = "FULL" | "READ" | "OWN" | "MANAGE" | "NONE";

export interface MatrixCell {
  symbol: MatrixSymbol;
  scope: Scope;
  permissions: PermissionCode[];
}

const APPROVE_ACTIONS = new Set([
  "approve", "reject", "manage", "config", "audit",
]);

function actionOf(perm: PermissionCode): string {
  const idx = perm.lastIndexOf(":");
  return idx >= 0 ? perm.slice(idx + 1) : perm;
}

/** 根据 scope + 权限点 推出矩阵单元符号。 */
export function deriveCell(role: RoleCode, resource: ResourceCode): MatrixCell {
  const scope = ROLE_RESOURCE_SCOPE[role][resource];
  const perms = ROLE_RESOURCE_PERMISSIONS[role][resource] ?? [];

  if (scope === "NONE" && perms.length === 0) {
    return { symbol: "NONE", scope, permissions: [] };
  }

  const hasApproveLike = perms.some((p) => APPROVE_ACTIONS.has(actionOf(p)));
  const hasWriteLike = perms.some((p) =>
    ["write", "create", "respond", "checkin"].includes(actionOf(p))
  );

  if (hasApproveLike) return { symbol: "MANAGE", scope, permissions: perms };
  if (scope === "OWN" || scope === "ORG") return { symbol: "OWN", scope, permissions: perms };
  if (scope === "ALL" && hasWriteLike) return { symbol: "FULL", scope, permissions: perms };
  if (scope === "ALL") return { symbol: "READ", scope, permissions: perms };

  return { symbol: "NONE", scope, permissions: perms };
}

export const MATRIX_SYMBOL_META: Record<MatrixSymbol, {
  label: string;
  description: string;
  bg: string;
  fg: string;
}> = {
  FULL:   { label: "✓ 全",  description: "完全权限(CRUD)",            bg: "#dcfce7", fg: "#166534" },
  READ:   { label: "📖 读", description: "只读权限",                    bg: "#dbeafe", fg: "#1e40af" },
  OWN:    { label: "◎ 己",  description: "仅自己/本组织数据",            bg: "#ffedd5", fg: "#9a3412" },
  MANAGE: { label: "★ 管",  description: "管理权限(审核 / 配置)",      bg: "#ede9fe", fg: "#5b21b6" },
  NONE:   { label: "× 无",  description: "无权限",                      bg: "#fee2e2", fg: "#991b1b" },
};

export const SCOPE_META: Record<Scope, { label: string; description: string }> = {
  ALL:  { label: "ALL",  description: "全平台数据,无 WHERE 过滤" },
  ORG:  { label: "ORG",  description: "仅本组织数据(WHERE buyer_organization_id = ...)" },
  OWN:  { label: "OWN",  description: "仅本企业/本人数据(WHERE supplier_id = ... 或 user_id = ...)" },
  NONE: { label: "NONE", description: "无访问权(权限点已拦截)" },
};

// ---------- 工具函数 ----------

export function scopeOf(roles: RoleCode[], resource: ResourceCode): Scope {
  const rank = { NONE: 0, OWN: 1, ORG: 2, ALL: 3 } as const;
  let best: Scope = "NONE";
  for (const r of roles) {
    const s = ROLE_RESOURCE_SCOPE[r]?.[resource] ?? "NONE";
    if (rank[s] > rank[best]) best = s;
  }
  return best;
}
