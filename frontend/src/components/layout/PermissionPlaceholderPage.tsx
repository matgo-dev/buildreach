"use client";
import { useState } from "react";
import { usePathname } from "@/i18n/navigation";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Play,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { findNavItemByPath } from "@/config/navigation";
import {
  MATRIX_SYMBOL_META,
  RESOURCES,
  SCOPE_META,
  deriveCell,
  scopeOf,
  type PermissionCode,
  type ResourceCode,
} from "@/config/permission-matrix";
import { debugApi, type ScopeCheck } from "@/lib/debugApi";
import { ApiError } from "@/lib/api";
import type { RoleCode } from "@/lib/auth";

interface Props {
  pathOverride?: string;
  title?: string;
  description?: string;
  moduleLabel?: string;
  /** 覆盖资源域(否则从 navigation 配置反查)。 */
  resource?: ResourceCode | null;
  /** 覆盖要求的权限点(否则从 navigation 配置反查)。 */
  requiredPermissions?: PermissionCode[];
  icon?: LucideIcon;
}

/**
 * 占位页统一组件(v3 §6,4 个维度):
 *   1. 页面访问(✅/❌)
 *   2. 权限点检查
 *   3. 数据范围 scope + 矩阵符号
 *   4. 后端 scope 调试接口(按钮)
 */
export function PermissionPlaceholderPage(props: Props = {}) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);

  const path = props.pathOverride ?? pathname;
  const navItem = findNavItemByPath(path);
  const Icon = props.icon ?? navItem?.icon ?? Sparkles;

  const title = props.title ?? navItem?.label ?? path;
  const description =
    props.description ??
    navItem?.description ??
    "(占位)此页面用于演示路由 + 侧边栏权限可视化,后续业务模块上线时替换。";
  const resource = props.resource !== undefined ? props.resource : navItem?.resource ?? null;
  const requiredPermissions = props.requiredPermissions ?? navItem?.requiredPermissions ?? [];

  // 维度 2:权限点
  const missingPerms = requiredPermissions.filter((p) => !(user?.permissions ?? []).includes(p));
  const permOk = missingPerms.length === 0;

  // 维度 3:scope
  const userRoles = (user?.roles ?? []) as RoleCode[];
  const scope = resource ? scopeOf(userRoles, resource) : null;
  const cell =
    resource && userRoles.length > 0 ? deriveCell(userRoles[0], resource) : null;
  const symbolMeta = cell ? MATRIX_SYMBOL_META[cell.symbol] : null;

  const overallOk = permOk && (scope === null || scope !== "NONE");
  const accent = overallOk ? "#10B981" : "#EF4444";
  const moduleLabel =
    props.moduleLabel ?? (resource ? RESOURCES[resource].module : guessModule(path));

  return (
    <div className="space-y-4">
      {/* 标题区 */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>{moduleLabel}</span>
        <ChevronRight className="h-3.5 w-3.5" />
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
          {path}
        </code>
      </div>
      <div className="flex items-start gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
          style={{ backgroundColor: `${accent}15` }}
        >
          <Icon className="h-6 w-6" style={{ color: accent }} />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
      </div>

      {/* 维度 1:页面访问 */}
      <Section
        accent={accent}
        title={overallOk ? "维度 1:你有权访问此页面" : "维度 1:你没有访问此页面的权限"}
        sub={
          overallOk
            ? "路由守卫与侧边栏渲染结果一致 ✓"
            : "理论上路由守卫已拦截,你看到这一页说明调试模式硬闯进来"
        }
        ok={overallOk}
      >
        <div className="text-xs text-slate-500">
          当前用户:<strong>{user?.email ?? "(未登录)"}</strong>
          {user?.username && <> · {user.username}</>} · 角色 [{userRoles.join(", ") || "无"}]
        </div>
      </Section>

      {/* 维度 2:权限点 */}
      <Section
        accent={permOk ? "#10B981" : "#EF4444"}
        title="维度 2:权限点(动作许可)"
        sub="路由守卫检查 user.permissions 是否包含全部要求的权限点"
        ok={permOk}
      >
        {requiredPermissions.length === 0 ? (
          <div className="text-sm text-slate-500">此页面不要求权限点(任意已登录可访问)</div>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {requiredPermissions.map((p) => {
              const has = (user?.permissions ?? []).includes(p);
              return (
                <li key={p} className="flex items-center gap-2">
                  {has ? (
                    <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  )}
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                    {p}
                  </code>
                  <span className={has ? "text-[#10B981]" : "text-red-500"}>
                    {has ? "已拥有" : "缺失"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      {/* 维度 3:数据范围 scope */}
      <Section
        accent={scope && scope !== "NONE" ? "#10B981" : "#94a3b8"}
        title="维度 3:数据范围(scope)"
        sub="决定后端服务层 WHERE 过滤条件 — 由角色 + 资源查表得出"
        ok={scope !== "NONE"}
      >
        {scope === null ? (
          <div className="text-sm text-slate-500">此页面不绑定任何资源域</div>
        ) : (
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <InfoRow label="资源域">
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{resource}</code>
              <span className="ml-1 text-slate-500">({RESOURCES[resource!].name})</span>
            </InfoRow>
            <InfoRow label="scope 值">
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{scope}</code>
            </InfoRow>
            <InfoRow label="矩阵符号">
              {symbolMeta && (
                <span
                  className="rounded px-2 py-0.5 text-xs font-medium"
                  style={{ backgroundColor: symbolMeta.bg, color: symbolMeta.fg }}
                >
                  {symbolMeta.label}({symbolMeta.description})
                </span>
              )}
            </InfoRow>
            <InfoRow label="说明">
              <span className="text-slate-600">{SCOPE_META[scope].description}</span>
            </InfoRow>
          </dl>
        )}
      </Section>

      {/* 维度 4:后端调试 */}
      {resource && (
        <ScopeDebugSection resource={resource} />
      )}

      {/* 占位说明 */}
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        <p className="font-medium text-slate-700">(占位)</p>
        <p className="mt-1">{description}</p>
        <p className="mt-3 text-xs text-slate-400">
          本页用于"导航 + 侧边栏 + 路由守卫 + scope"四件套的可视化验证,不实现任何业务功能。
        </p>
      </div>
    </div>
  );
}

function ScopeDebugSection({ resource }: { resource: ResourceCode }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScopeCheck | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await debugApi.scope(resource);
      setResult(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section
      accent="#003366"
      title="维度 4:后端 scope 调试接口"
      sub="调用 GET /api/v1/_debug/scope 查后端真实返回(不返回业务数据)"
      ok={null}
    >
      <button
        onClick={onClick}
        disabled={loading}
        className="inline-flex h-9 items-center gap-2 rounded-md bg-[#003366] px-4 text-xs font-semibold text-white hover:bg-[#002244] disabled:opacity-60"
      >
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
        调用 /_debug/scope?resource={resource}
      </button>

      {error && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
      )}
      {result && (
        <pre className="mt-3 overflow-x-auto rounded-md bg-slate-900 p-4 font-mono text-xs leading-relaxed text-slate-100">
{JSON.stringify(result, null, 2)}
        </pre>
      )}
    </Section>
  );
}

function Section({
  accent,
  title,
  sub,
  ok,
  children,
}: {
  accent: string;
  title: string;
  sub: string;
  ok: boolean | null;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-2xl border-l-4 bg-white p-5 shadow-sm"
      style={{ borderLeftColor: accent }}
    >
      <div className="flex items-start gap-3">
        {ok === null ? null : ok ? (
          <CheckCircle2 className="mt-0.5 h-5 w-5 text-[#10B981]" />
        ) : (
          <AlertCircle className="mt-0.5 h-5 w-5 text-red-500" />
        )}
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{sub}</p>
        </div>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

function guessModule(pathname: string): string {
  if (pathname.startsWith("/buyer")) return "BUYER 工作台";
  if (pathname.startsWith("/supplier")) return "SUPPLIER 工作台";
  if (pathname.startsWith("/operator")) return "OPERATOR 后台";
  if (pathname.startsWith("/admin")) return "ADMIN 后台";
  if (pathname.startsWith("/test")) return "RBAC 调试";
  return "公开区";
}
