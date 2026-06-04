"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Building2,
  CheckCircle2,
  LogOut,
  Settings,
  ShieldCheck,
  ShoppingCart,
  UserCog,
  XCircle,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useLogout } from "@/hooks/useAuth";
import type { RoleCode } from "@/lib/auth";

const ENDPOINTS: { key: string; label: string; path: string; role: RoleCode }[] = [
  { key: "buyer", label: "/api/v1/test/buyer-only", path: "/api/v1/test/buyer-only", role: "BUYER" },
  { key: "supplier", label: "/api/v1/test/supplier-only", path: "/api/v1/test/supplier-only", role: "SUPPLIER" },
  { key: "operator", label: "/api/v1/test/operator-only", path: "/api/v1/test/operator-only", role: "OPERATOR" },
  { key: "admin", label: "/api/v1/test/admin-only", path: "/api/v1/test/admin-only", role: "ADMIN" },
];

const ROLE_META: Record<RoleCode, { color: string; icon: typeof ShoppingCart; label: string }> = {
  BUYER: { color: "#003366", icon: ShoppingCart, label: "采购方" },
  SUPPLIER: { color: "#FF6B35", icon: Building2, label: "供应商" },
  OPERATOR: { color: "#0F4C81", icon: UserCog, label: "平台运营" },
  ADMIN: { color: "#475569", icon: ShieldCheck, label: "系统管理员" },
};

interface CallResult {
  status: "success" | "error";
  httpStatus?: number;
  bizCode?: number;
  message: string;
  traceId?: string;
}

export function RbacTestPanel({ pageRole }: { pageRole: RoleCode }) {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const [results, setResults] = useState<Record<string, CallResult>>({});
  const [loading, setLoading] = useState<string | null>(null);

  if (!user) return null;

  const meta = ROLE_META[pageRole];
  const Icon = meta.icon;

  const call = async (key: string, path: string) => {
    setLoading(key);
    try {
      await api.get(path);
      setResults((p) => ({ ...p, [key]: { status: "success", message: "200 OK" } }));
    } catch (err) {
      if (err instanceof ApiError) {
        setResults((p) => ({
          ...p,
          [key]: {
            status: "error",
            httpStatus: err.status,
            bizCode: err.code,
            message: err.message,
            traceId: err.traceId,
          },
        }));
      } else {
        setResults((p) => ({ ...p, [key]: { status: "error", message: String(err) } }));
      }
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* 顶部条 */}
      <header className="bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
            ← 返回首页
          </Link>
          <div className="flex items-center gap-2">
            <Link
              href="/account"
              className="flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
            >
              <Settings className="h-3.5 w-3.5" /> 账户设置
            </Link>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
            >
              <LogOut className="h-3.5 w-3.5" /> 登出
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        {/* 当前用户信息 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start gap-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
              style={{ backgroundColor: `${meta.color}15` }}
            >
              <Icon className="h-6 w-6" style={{ color: meta.color }} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-slate-900">RBAC 测试页 · {meta.label}</h1>
                <span
                  className="rounded px-2 py-0.5 text-xs font-semibold"
                  style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
                >
                  {pageRole}_ONLY
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                以 <strong>{user.email}</strong> 登录 · 角色 [{user.roles.join(", ")}]
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <InfoRow label="姓名" value={user.name} />
            <InfoRow label="状态" value={user.status} />
            <InfoRow label="邮箱" value={user.email} />
            <InfoRow label="用户名" value={user.username ?? "(未设置)"} />
            <InfoRow label="组织" value={user.organization?.name ?? "(无)"} />
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-semibold text-slate-700">
              我的权限点(共 {user.permissions.length} 个)
            </h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {user.permissions.map((p) => (
                <span
                  key={p}
                  className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* 测试接口 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">测试 4 个角色接口</h2>
          <p className="mt-1 text-sm text-slate-500">
            自己角色应 <strong className="text-[#10B981]">200</strong>,其他应{" "}
            <strong className="text-red-500">403</strong>。
          </p>

          <div className="mt-5 space-y-3">
            {ENDPOINTS.map((ep) => {
              const r = results[ep.key];
              const isCurrent = ep.role === pageRole;
              const epMeta = ROLE_META[ep.role];
              return (
                <div key={ep.key} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: epMeta.color }}
                      />
                      <code className="text-sm text-slate-700">GET {ep.label}</code>
                      {isCurrent && (
                        <span className="rounded bg-[#10B981]/10 px-1.5 py-0.5 text-xs font-semibold text-[#10B981]">
                          应通过
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => call(ep.key, ep.path)}
                      disabled={loading === ep.key}
                      className="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
                    >
                      {loading === ep.key ? "请求中..." : "调用"}
                    </button>
                  </div>

                  {r && (
                    <div className="mt-3">
                      {r.status === "success" ? (
                        <div className="flex items-center gap-2 rounded-md bg-[#10B981]/10 px-3 py-2 text-sm text-[#047857]">
                          <CheckCircle2 className="h-4 w-4" />
                          <span className="font-mono">200 — {r.message}</span>
                        </div>
                      ) : (
                        <div className="flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                          <XCircle className="mt-0.5 h-4 w-4" />
                          <div className="font-mono text-xs">
                            <div>
                              HTTP {r.httpStatus} · code {r.bizCode} · {r.message}
                            </div>
                            {r.traceId && (
                              <div className="mt-1 text-slate-500">trace_id: {r.traceId}</div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-slate-700">{value}</div>
    </div>
  );
}
