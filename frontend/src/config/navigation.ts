/**
 * 路由 + 侧边栏配置(v3 §9)。
 *
 * 权限点 / scope 矩阵的"权威"在 permission-matrix.ts。
 * 本文件只定义"哪些 tab 在哪个 workspace,绑哪个 resource + 权限点"。
 */
import {
  type LucideIcon,
  Grid3x3,
  Package,
  Receipt,
  ScrollText,
  Send,
  ShoppingBag,
  ShoppingCart,
  Users,
} from "lucide-react";

import {
  Permissions,
  type PermissionCode,
  type ResourceCode,
} from "@/config/permission-matrix";
import type { RoleCode } from "@/lib/auth";

export type WorkspaceCode = "BUYER" | "SUPPLIER" | "OPERATOR" | "ADMIN" | "PUBLIC";

export interface NavItem {
  path: string;
  /** i18n key,用于 useTranslations("nav") */
  labelKey: string;
  /** 硬编码中文(fallback + 配置可读性) */
  label: string;
  /** 英文副标,中文 locale 下作为副标题显示 */
  labelEn?: string;
  icon: LucideIcon;
  /** 该 tab 绑定的资源域(用于 sidebar 显隐判断 + 占位页 scope 展示)。 */
  resource: ResourceCode | null;
  /** 路由守卫要求的权限点(全部满足才能进)。 */
  requiredPermissions: PermissionCode[];
  /** 短描述,显示在占位页 */
  description: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export interface Workspace {
  code: WorkspaceCode;
  label: string;
  pathPrefix: string;
  themeColor: string;
  groups: NavGroup[];
}

// ========== 公开区 ==========

export const PUBLIC_NAV: NavItem[] = [
  {
    path: "/mall",
    labelKey: "mall",
    label: "严选商城",
    labelEn: "Mall",
    icon: ShoppingBag,
    resource: "product",
    requiredPermissions: [],
    description: "B2B 工业品采购前台",
  },
];

// ========== 工作台 ==========

export const WORKSPACES: Workspace[] = [
  {
    code: "BUYER",
    label: "采购方工作台",
    pathPrefix: "/buyer",
    themeColor: "#006773",
    groups: [
      {
        label: "BUYER 工作台",
        items: [
          { path: "/mall",                    labelKey: "mall",             label: "严选商城",   labelEn: "Mall",               icon: ShoppingBag,   resource: "product", requiredPermissions: [],                        description: "B2B 工业品采购前台" },
          { path: "/buyer/cart",              labelKey: "inquiryBasket",    label: "询价篮",     labelEn: "Inquiry Basket",     icon: ShoppingCart,  resource: "cart",    requiredPermissions: [Permissions.CART_READ],    description: "已加入清单待询价的商品" },
          { path: "/buyer/rfqs",              labelKey: "rfqManagement",    label: "询价管理",   labelEn: "RFQ",                icon: Send,          resource: "rfq",     requiredPermissions: [Permissions.RFQ_READ],     description: "我发起的询价单与报价比较" },
        ],
      },
    ],
  },
  {
    code: "OPERATOR",
    label: "运营后台",
    pathPrefix: "/operator",
    themeColor: "#0F4C81",
    groups: [
      {
        label: "OPERATOR 后台",
        items: [
          { path: "/operator/products",        labelKey: "productManagement", label: "商品管理",   labelEn: "Products",      icon: Package,         resource: "product",  requiredPermissions: [Permissions.PRODUCT_READ],         description: "SPU 列表 / 上下架 / 进入编辑详情" },
          { path: "/operator/rfqs",            labelKey: "rfqManagement",   label: "询价管理",     labelEn: "RFQ",           icon: Send,            resource: "rfq",      requiredPermissions: [Permissions.RFQ_READ],             description: "全平台询价单受理与管理" },
        ],
      },
    ],
  },
  {
    code: "ADMIN",
    label: "系统管理后台",
    pathPrefix: "/admin",
    themeColor: "#475569",
    groups: [
      {
        label: "ADMIN 后台",
        items: [
          { path: "/admin/users",       labelKey: "userManagement",       label: "用户管理", labelEn: "Users",       icon: Users,       resource: "user",       requiredPermissions: [Permissions.USER_MANAGE],       description: "内部账号(ADMIN/OPERATOR)创建与停用" },
          { path: "/admin/audit-logs",  labelKey: "auditLogs",            label: "审计日志", labelEn: "Audit Logs",  icon: ScrollText,  resource: "system",     requiredPermissions: [Permissions.SYSTEM_AUDIT],      description: "全平台敏感操作审计记录" },
        ],
      },
      {
        label: "RBAC 调试",
        items: [
          { path: "/admin/permission-matrix", labelKey: "permissionMatrix",  label: "权限矩阵全景",      labelEn: "Matrix",        icon: Grid3x3,    resource: null, requiredPermissions: [], description: "4 角色 × 15 资源域 × 5 符号的全景视图" },
        ],
      },
    ],
  },
];

// ========== 辅助 ==========

export const PRIMARY_WORKSPACE_OF_ROLE: Record<RoleCode, WorkspaceCode> = {
  BUYER: "BUYER",
  SUPPLIER: "SUPPLIER",
  OPERATOR: "OPERATOR",
  ADMIN: "ADMIN",
};

export function defaultDashboardOf(roles: RoleCode[]): string {
  if (roles.includes("ADMIN")) return "/admin/users";
  if (roles.includes("OPERATOR")) return "/operator/products";
  if (roles.includes("SUPPLIER")) return "/mall";
  if (roles.includes("BUYER")) return "/mall";
  return "/";
}

/** 用户菜单"工作台"入口,跳到该角色的工作台首页。 */
export function workspaceDashboardOf(roles: RoleCode[]): string {
  if (roles.includes("ADMIN")) return "/admin/users";
  if (roles.includes("OPERATOR")) return "/operator/products";
  if (roles.includes("SUPPLIER")) return "/mall";
  if (roles.includes("BUYER")) return "/buyer/rfqs";
  return "/";
}

export function findWorkspaceByPath(pathname: string): Workspace | null {
  return WORKSPACES.find((w) => pathname.startsWith(w.pathPrefix)) ?? null;
}

export function findNavItemByPath(pathname: string): NavItem | null {
  for (const item of PUBLIC_NAV) if (item.path === pathname) return item;
  for (const w of WORKSPACES)
    for (const g of w.groups)
      for (const i of g.items) if (i.path === pathname) return i;
  return null;
}
