"use client";
import { Link, usePathname } from "@/i18n/navigation";
import { Lock } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { useDebugMode } from "@/stores/uiStore";
import {
  WORKSPACES,
  type NavItem,
  type Workspace,
} from "@/config/navigation";
import { scopeOf } from "@/config/permission-matrix";
import type { RoleCode } from "@/lib/auth";

/**
 * 侧边栏(v3 §8)。深色主题对齐参考工程 overseas-supply-platform 的 SupplierSidebar/BuyerSidebar/AdminSidebar。
 *
 * tab 可见性:
 *   1. 没绑 resource 且无 requiredPermissions → 一律可见
 *   2. 绑了 resource → scope=NONE 无权;否则有权
 *   3. 有 requiredPermissions(无 resource)→ 检查权限点全部满足
 *
 * 调试模式:无权置灰 + lock 图标 + hover 提示;线上模式:无权不渲染。
 */
export function AppSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const [debugMode] = useDebugMode();

  if (!user) return null;

  const userPerms = new Set(user.permissions);
  const userRoles = user.roles as RoleCode[];
  // /mall 属于 BUYER 工作台，但路径不以 /buyer 开头，需特殊匹配
  const currentWs =
    WORKSPACES.find((w) => pathname.startsWith(w.pathPrefix)) ??
    (pathname.startsWith("/mall") && userRoles.includes("BUYER")
      ? WORKSPACES.find((w) => w.code === "BUYER")
      : undefined);

  const checkAccess = (item: NavItem): { ok: boolean; reason: string } => {
    if (item.resource) {
      const scope = scopeOf(userRoles, item.resource);
      if (scope === "NONE") return { ok: false, reason: `scope=NONE on ${item.resource}` };
    }
    if (item.requiredPermissions.length > 0) {
      const missing = item.requiredPermissions.find((p) => !userPerms.has(p));
      if (missing) return { ok: false, reason: `缺权限点 ${missing}` };
    }
    return { ok: true, reason: "" };
  };

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col overflow-y-auto bg-[#0A1929]">
      <UserCard />
      <nav className="flex-1 space-y-1 overflow-y-auto p-3 text-sm">
        {currentWs && (
          <WorkspaceGroups
            workspace={currentWs}
            currentPath={pathname}
            debugMode={debugMode}
            checkAccess={checkAccess}
          />
        )}

        {debugMode && (
          <>
            <div className="mt-4 px-3 pb-1 pt-3 text-[10px] uppercase tracking-widest text-slate-500">
              其他工作台(调试可见)
            </div>
            {WORKSPACES.filter((w) => w.code !== currentWs?.code).map((w) => (
              <WorkspaceGroups
                key={w.code}
                workspace={w}
                currentPath={pathname}
                debugMode={debugMode}
                checkAccess={checkAccess}
                muted
              />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}

/** 顶部用户信息卡:头像首字母 + 名字 + 角色徽章。 */
function UserCard() {
  const user = useAuthStore((s) => s.user);
  if (!user) return null;

  const displayName = user.username || user.email || "用户";
  const initial = (displayName[0] ?? "U").toUpperCase();
  const primaryRole = user.roles[0] as RoleCode | undefined;
  const meta = primaryRole ? ROLE_BADGE[primaryRole] : null;

  return (
    <div className="border-b border-white/10 p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0F4C81] text-sm font-medium text-white">
          {initial}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">{displayName}</p>
          {meta && (
            <span
              className={`mt-0.5 inline-block rounded px-1.5 py-0.5 text-xs ${meta.cls}`}
            >
              {meta.label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

const ROLE_BADGE: Record<RoleCode, { label: string; cls: string }> = {
  BUYER:    { label: "采购方",     cls: "bg-[#FF6B35]/20 text-[#FF6B35]" },
  SUPPLIER: { label: "供应商",     cls: "bg-[#10B981]/20 text-[#10B981]" },
  OPERATOR: { label: "平台运营",   cls: "bg-sky-500/20 text-sky-400" },
  ADMIN:    { label: "系统管理员", cls: "bg-yellow-500/20 text-yellow-400" },
};

function WorkspaceGroups({
  workspace,
  currentPath,
  debugMode,
  checkAccess,
  muted = false,
}: {
  workspace: Workspace;
  currentPath: string;
  debugMode: boolean;
  checkAccess: (item: NavItem) => { ok: boolean; reason: string };
  muted?: boolean;
}) {
  return (
    <>
      {workspace.groups.map((g) => (
        <div key={g.label} className="mt-2 space-y-0.5">
          {workspace.groups.length > 1 && (
            <SectionHeader label={g.label} accentColor={workspace.themeColor} muted={muted} />
          )}
          {g.items.map((item) => {
            const access = checkAccess(item);
            if (!access.ok && !debugMode) return null;
            return (
              <NavLink
                key={item.path}
                item={item}
                currentPath={currentPath}
                access={access}
                debugMode={debugMode}
              />
            );
          })}
        </div>
      ))}
    </>
  );
}

function SectionHeader({
  label,
  accentColor,
  muted = false,
}: {
  label: string;
  accentColor?: string;
  muted?: boolean;
}) {
  return (
    <div
      className={
        "mb-1 mt-2 flex items-center gap-2 px-3 text-[10px] uppercase tracking-widest " +
        (muted ? "text-slate-600" : "text-slate-500")
      }
    >
      {accentColor && (
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
      )}
      {label}
    </div>
  );
}

function NavLink({
  item,
  currentPath,
  access,
  debugMode,
}: {
  item: NavItem;
  currentPath: string;
  access: { ok: boolean; reason: string };
  debugMode: boolean;
}) {
  // 子路径也算激活(/supplier/products/123 时高亮"商品管理")
  const isActive =
    currentPath === item.path || currentPath.startsWith(item.path + "/");
  const Icon = item.icon;

  const TextBlock = (
    <span className="flex-1 leading-tight">
      <span className="block truncate">{item.label}</span>
      {item.labelEn && (
        <span
          className={
            "block text-[9px] font-normal " +
            (isActive ? "text-white/60" : access.ok ? "text-gray-600" : "text-gray-700")
          }
        >
          {item.labelEn}
        </span>
      )}
    </span>
  );

  if (access.ok) {
    return (
      <Link
        href={item.path}
        className={
          "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors " +
          (isActive
            ? "bg-[#0F4C81] text-white"
            : "text-gray-400 hover:bg-white/5 hover:text-white")
        }
      >
        <Icon className="h-4 w-4 shrink-0" />
        {TextBlock}
      </Link>
    );
  }

  if (debugMode) {
    return (
      <div
        title={access.reason}
        className="flex cursor-not-allowed select-none items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-gray-600"
      >
        <Icon className="h-4 w-4 shrink-0" />
        {TextBlock}
        <Lock className="h-3 w-3 shrink-0 opacity-60" />
      </div>
    );
  }

  return null;
}
