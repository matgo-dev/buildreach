"use client";
import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import {
  MATRIX_SYMBOL_META,
  RESOURCES,
  ROLE_RESOURCE_SCOPE,
  SCOPE_META,
  deriveCell,
  type MatrixSymbol,
  type ResourceCode,
} from "@/config/permission-matrix";
import type { RoleCode } from "@/lib/auth";

const ROLES: RoleCode[] = ["BUYER", "SUPPLIER", "OPERATOR", "ADMIN"];

const ROLE_LABEL: Record<RoleCode, { name: string; desc: string; color: string }> = {
  BUYER:    { name: "项目部采购员", desc: "本组织项目数据",       color: "#003366" },
  SUPPLIER: { name: "供应商",       desc: "本企业数据",             color: "#FF6B35" },
  OPERATOR: { name: "平台运营",     desc: "全平台数据(审核权)",   color: "#0F4C81" },
  ADMIN:    { name: "系统管理员",   desc: "系统级权限",             color: "#475569" },
};

// ADMIN 专属页:其他角色拦到 /no-permission
function Inner() {
  const [selected, setSelected] = useState<{ role: RoleCode; resource: ResourceCode } | null>(null);

  const resources = useMemo(() => Object.values(RESOURCES), []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">
          RBAC 权限控制矩阵
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          4 角色 × 15 资源域,符号 = scope + 权限点动作类别推导。点击任一格查看详情。
        </p>
      </header>

      {/* 图例 */}
      <div className="flex flex-wrap gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        {(Object.keys(MATRIX_SYMBOL_META) as MatrixSymbol[]).map((s) => {
          const meta = MATRIX_SYMBOL_META[s];
          return (
            <div key={s} className="flex items-center gap-2 text-xs">
              <span
                className="rounded px-2 py-0.5 font-medium"
                style={{ backgroundColor: meta.bg, color: meta.fg }}
              >
                {meta.label}
              </span>
              <span className="text-slate-600">{meta.description}</span>
            </div>
          );
        })}
      </div>

      {/* 矩阵 */}
      <div className="overflow-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-r border-slate-200 bg-slate-50 px-3 py-3 text-left font-semibold text-slate-700">
                角色 \ 资源
              </th>
              {resources.map((r) => (
                <th
                  key={r.code}
                  className="border-b border-slate-200 bg-slate-50 px-2 py-3 text-center font-medium text-slate-700"
                  title={`${r.name} · ${r.module}`}
                >
                  <div className="text-slate-900">{r.name}</div>
                  <div className="font-mono text-[10px] text-slate-400">{r.code}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROLES.map((role) => {
              const meta = ROLE_LABEL[role];
              return (
                <tr key={role}>
                  <td
                    className="sticky left-0 z-10 border-r border-b border-slate-200 bg-white px-3 py-3 align-top"
                    style={{ borderLeft: `4px solid ${meta.color}` }}
                  >
                    <div className="font-semibold text-slate-900">{meta.name}</div>
                    <div className="mt-0.5 font-mono text-[10px] text-slate-400">{role}</div>
                    <div className="mt-1 text-[10px] text-slate-500">{meta.desc}</div>
                  </td>
                  {resources.map((r) => {
                    const cell = deriveCell(role, r.code);
                    const sym = MATRIX_SYMBOL_META[cell.symbol];
                    return (
                      <td
                        key={r.code}
                        className="border-b border-slate-100 p-1.5 text-center"
                      >
                        <button
                          onClick={() => setSelected({ role, resource: r.code })}
                          className="block w-full rounded px-1.5 py-2 text-[11px] font-semibold transition-transform hover:scale-105"
                          style={{ backgroundColor: sym.bg, color: sym.fg }}
                          title={`${meta.name} → ${r.name} → ${sym.description}`}
                        >
                          {sym.label}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 三条原则 */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
        <p className="font-semibold">RBAC 核心原则:</p>
        <ul className="mt-2 space-y-1">
          <li>· 项目部只能查看本组织项目(scope=ORG,后端 WHERE buyer_organization_id 过滤)</li>
          <li>· 供应商只能查看本企业数据(scope=OWN,后端 WHERE supplier_id 过滤)</li>
          <li>· 运营可审核但不可修改系统配置(需 ADMIN);ADMIN 严格不触业务数据(Q25)</li>
        </ul>
      </div>

      {selected && (
        <CellDetailModal
          role={selected.role}
          resource={selected.resource}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function CellDetailModal({
  role,
  resource,
  onClose,
}: {
  role: RoleCode;
  resource: ResourceCode;
  onClose: () => void;
}) {
  const cell = deriveCell(role, resource);
  const sym = MATRIX_SYMBOL_META[cell.symbol];
  const rMeta = RESOURCES[resource];
  const roleMeta = ROLE_LABEL[role];
  const scope = ROLE_RESOURCE_SCOPE[role][resource];
  const scopeMeta = SCOPE_META[scope];

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-slate-200 p-5">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              {roleMeta.name} × {rMeta.name}
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              {role} · {resource}({rMeta.module})
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5 text-sm">
          <Row label="矩阵符号">
            <span
              className="rounded px-2 py-1 font-medium"
              style={{ backgroundColor: sym.bg, color: sym.fg }}
            >
              {sym.label}
            </span>
            <span className="ml-2 text-slate-600">{sym.description}</span>
          </Row>
          <Row label="数据范围 scope">
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{scope}</code>
            <p className="mt-1 text-xs text-slate-500">{scopeMeta.description}</p>
          </Row>
          <Row label={`持有的权限点(${cell.permissions.length} 个)`}>
            {cell.permissions.length === 0 ? (
              <span className="text-xs text-slate-400">无</span>
            ) : (
              <ul className="space-y-0.5">
                {cell.permissions.map((p) => (
                  <li key={p}>
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{p}</code>
                  </li>
                ))}
              </ul>
            )}
          </Row>
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export default function PermissionMatrixPage() {
  return (
    <RouteGuard allowRoles={["ADMIN"]}>
      <Inner />
    </RouteGuard>
  );
}
