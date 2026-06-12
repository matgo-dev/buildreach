/**
 * 路由 + 侧边栏配置(v3 §9)。
 *
 * 权限点 / scope 矩阵的"权威"在 permission-matrix.ts。
 * 本文件只定义"哪些 tab 在哪个 workspace,绑哪个 resource + 权限点"。
 */
import {
  type LucideIcon,
  BarChart3,
  ClipboardList,
  FileBadge,
  Gauge,
  Globe,
  Grid3x3,
  HelpCircle,
  Inspect,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  Package,

  Receipt,
  ScrollText,
  Send,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Store,
  UserCircle2,
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
  label: string;
  /** 英文副标,公开区顶部导航中英双语展示用 */
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
    themeColor: "#003366",
    groups: [
      {
        label: "BUYER 工作台",
        items: [
          { path: "/mall",                  label: "严选商城",   labelEn: "Mall",           icon: ShoppingBag,     resource: "product",       requiredPermissions: [],                          description: "B2B 工业品采购前台" },
          { path: "/buyer/cart",           label: "询价篮",     labelEn: "Inquiry Basket",  icon: ShoppingCart,    resource: "cart",          requiredPermissions: [Permissions.CART_READ],          description: "已加入清单待询价的商品" },
          { path: "/buyer/rfqs",           label: "询价管理",   labelEn: "RFQ",            icon: Send,            resource: "rfq",           requiredPermissions: [Permissions.RFQ_READ],           description: "我发起的询价单与报价比较" },
          { path: "/buyer/category-analysis", label: "品类分析", labelEn: "Category Analysis", icon: BarChart3, resource: null, requiredPermissions: [], description: "品类供应链全景分析（demo）" },
          { path: "/buyer/orders",         label: "订单管理",   labelEn: "Orders",         icon: Receipt,         resource: "order",         requiredPermissions: [Permissions.ORDER_READ],         description: "订单列表 + 12 节点履约追踪" },
        ],
      },
    ],
  },
  {
    code: "SUPPLIER",
    label: "供应商工作台",
    pathPrefix: "/supplier",
    themeColor: "#FF6B35",
    groups: [
      {
        label: "SUPPLIER 工作台",
        items: [
          { path: "/supplier/dashboard",  label: "工作台",     labelEn: "Dashboard",   icon: LayoutDashboard, resource: null,         requiredPermissions: [],                              description: "待响应 RFQ、在产订单、评分总览" },
          { path: "/supplier/onboarding", label: "企业入驻",   labelEn: "Onboarding",  icon: FileBadge,       resource: "supplier",   requiredPermissions: [Permissions.SUPPLIER_WRITE],     description: "完善企业资料与上传资质" },
          { path: "/supplier/membership", label: "会员中心",   labelEn: "Membership",  icon: KeyRound,        resource: "membership", requiredPermissions: [Permissions.MEMBERSHIP_READ],    description: "会员状态与缴费记录" },
          { path: "/supplier/products",   label: "商品管理",   labelEn: "Products",    icon: Package,         resource: "product",    requiredPermissions: [Permissions.PRODUCT_READ],       description: "SKU 列表 / 新增 / 国别准入资质" },
          // 单边模型:SUPPLIER 不参与询价报价,rfqs/quotes 导航已移除
          { path: "/supplier/orders",     label: "订单管理",   labelEn: "Orders",      icon: Receipt,         resource: "order",      requiredPermissions: [Permissions.ORDER_READ],         description: "订单列表与节点打卡" },
          { path: "/supplier/profile",    label: "企业档案",   labelEn: "Profile",     icon: UserCircle2,     resource: "supplier",   requiredPermissions: [Permissions.SUPPLIER_READ],      description: "企业资料 / 评分查看" },
          // 成员管理:本轮占位(PRD v1.3 §5.5)。**不挂权限点**,T-MEMBER 待办时再细化
          { path: "/supplier/members",    label: "成员管理",   labelEn: "Members",     icon: Users,           resource: null,         requiredPermissions: [],                              description: "功能即将上线 · owner 可在此邀请、移除企业内员工" },
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
          { path: "/operator/dashboard",       label: "管理首页",     labelEn: "Dashboard",     icon: LayoutDashboard, resource: null,       requiredPermissions: [],                                description: "全平台数据概览" },
          { path: "/operator/supplier-review", label: "供应商审核",   labelEn: "Suppliers",     icon: Inspect,         resource: "supplier", requiredPermissions: [Permissions.SUPPLIER_APPROVE],     description: "入驻审批 / 评分 / 分层" },
          { path: "/operator/products",        label: "商品管理",     labelEn: "Products",      icon: Package,         resource: "product",  requiredPermissions: [Permissions.PRODUCT_READ],         description: "SPU 列表 / 上下架 / 进入编辑详情" },
          { path: "/operator/product-review",  label: "商品审核",     labelEn: "Products",      icon: Inspect,         resource: "product",  requiredPermissions: [Permissions.PRODUCT_APPROVE],      description: "SKU 上架 + 国别准入资质审核" },
          { path: "/operator/rfqs",            label: "询价管理",     labelEn: "RFQ",           icon: Send,            resource: "rfq",      requiredPermissions: [Permissions.RFQ_READ],             description: "全平台询价单受理与管理" },
          { path: "/operator/orders",          label: "订单总览",     labelEn: "Orders",        icon: Receipt,         resource: "order",    requiredPermissions: [Permissions.ORDER_READ],           description: "全平台订单监控" },
          { path: "/operator/countries",       label: "国别数据维护", labelEn: "Countries",     icon: Globe,           resource: "country",  requiredPermissions: [Permissions.COUNTRY_WRITE],        description: "8 国 × 品类准入规则维护" },
          { path: "/operator/risk-cockpit",    label: "风控驾驶舱",   labelEn: "Risk Cockpit",  icon: Gauge,           resource: "risk",     requiredPermissions: [Permissions.RISK_READ],            description: "马甲关系 / 价格异常 / 合规雷达" },
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
          { path: "/admin/users",       label: "用户管理", labelEn: "Users",       icon: Users,       resource: "user",       requiredPermissions: [Permissions.USER_MANAGE],       description: "内部账号(ADMIN/OPERATOR)创建与停用" },
          { path: "/admin/roles",       label: "角色管理", labelEn: "Roles",       icon: ShieldAlert, resource: "role",       requiredPermissions: [Permissions.ROLE_MANAGE],       description: "角色 → 权限点关系(目前由启动同步管理)" },
          { path: "/admin/permissions", label: "权限管理", labelEn: "Permissions", icon: KeyRound,    resource: "permission", requiredPermissions: [Permissions.PERMISSION_MANAGE], description: "权限点清单总览" },
          { path: "/admin/config",      label: "系统配置", labelEn: "Settings",    icon: Settings2,   resource: "system",     requiredPermissions: [Permissions.SYSTEM_CONFIG],     description: "JWT / 限流 / Trace 等系统级配置(只读展示)" },
          { path: "/admin/audit-logs",  label: "审计日志", labelEn: "Audit Logs",  icon: ScrollText,  resource: "system",     requiredPermissions: [Permissions.SYSTEM_AUDIT],      description: "全平台敏感操作审计记录,支持按资源/动作/状态/邮箱/Trace ID 筛选" },
        ],
      },
      {
        label: "RBAC 调试",
        items: [
          { path: "/admin/permission-matrix", label: "权限矩阵全景",      labelEn: "Matrix",        icon: Grid3x3,    resource: null, requiredPermissions: [], description: "4 角色 × 15 资源域 × 5 符号的全景视图" },
          { path: "/test/buyer-only",         label: "BUYER API 调试",    labelEn: "Buyer API",     icon: HelpCircle, resource: null, requiredPermissions: [], description: "调用 buyer-only 后端接口验证" },
          { path: "/test/supplier-only",      label: "SUPPLIER API 调试", labelEn: "Supplier API",  icon: HelpCircle, resource: null, requiredPermissions: [], description: "调用 supplier-only 后端接口验证" },
          { path: "/test/operator-only",      label: "OPERATOR API 调试", labelEn: "Operator API",  icon: HelpCircle, resource: null, requiredPermissions: [], description: "调用 operator-only 后端接口验证" },
          { path: "/test/admin-only",         label: "ADMIN API 调试",    labelEn: "Admin API",     icon: HelpCircle, resource: null, requiredPermissions: [], description: "调用 admin-only 后端接口验证" },
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
  if (roles.includes("SUPPLIER")) return "/supplier/dashboard";
  if (roles.includes("BUYER")) return "/buyer/rfqs";
  return "/";
}

/** 用户菜单"工作台"入口,跳到该角色的工作台首页。 */
export function workspaceDashboardOf(roles: RoleCode[]): string {
  if (roles.includes("ADMIN")) return "/admin/users";
  if (roles.includes("OPERATOR")) return "/operator/products";
  if (roles.includes("SUPPLIER")) return "/supplier/dashboard";
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
