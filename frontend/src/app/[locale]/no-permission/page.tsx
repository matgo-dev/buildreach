"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, Home, LogIn } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";

function NoPermissionContent() {
  const router = useRouter();
  const params = useSearchParams();
  const required = params.get("required");
  const route = params.get("route");
  const reason = params.get("reason"); // "role" | null
  const user = useAuthStore((s) => s.user);

  const homePath = user ? defaultDashboardOf(user.roles) : "/";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="w-full max-w-lg">
        <div className="overflow-hidden rounded-2xl border-l-4 border-red-500 bg-white shadow-xl">
          <div className="bg-red-50 px-8 py-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100">
                <AlertTriangle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-red-900">无权访问</h1>
                <p className="text-sm text-red-700/80">前端路由守卫已拦截此次访问</p>
              </div>
            </div>
          </div>

          <div className="space-y-5 px-8 py-6">
            <div className="grid gap-3 text-sm">
              {route && (
                <Row label="目标路径">
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                    {route}
                  </code>
                </Row>
              )}
              {required && (
                <Row label="缺少权限点">
                  <code className="rounded bg-red-50 px-1.5 py-0.5 font-mono text-xs text-red-700">
                    {required}
                  </code>
                </Row>
              )}
              {reason === "role" && (
                <Row label="拦截原因">
                  <span className="text-slate-700">当前角色不在允许列表</span>
                </Row>
              )}
              <Row label="当前用户">
                <span className="text-slate-700">{user?.email ?? "(未登录)"}</span>
              </Row>
              <Row label="当前角色">
                <span className="text-slate-700">
                  {user?.roles?.length ? `[${user.roles.join(", ")}]` : "(无)"}
                </span>
              </Row>
            </div>

            <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-500">
              注:这是 UX 层防护,后端 API 守卫(<code>require_permission</code>)才是安全底线。
            </p>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => router.back()}
                className="inline-flex h-10 items-center gap-1.5 rounded-md border border-slate-200 px-4 text-sm text-slate-700 hover:bg-slate-50"
              >
                <ArrowLeft className="h-4 w-4" /> 返回上一页
              </button>
              <Link
                href={homePath}
                className="inline-flex h-10 items-center gap-1.5 rounded-md bg-[#003366] px-4 text-sm font-semibold text-white hover:bg-[#002244]"
              >
                <Home className="h-4 w-4" /> 我的工作台
              </Link>
              {!user && (
                <Link
                  href="/login"
                  className="inline-flex h-10 items-center gap-1.5 rounded-md bg-[#FF6B35] px-4 text-sm font-semibold text-white hover:bg-[#e05a25]"
                >
                  <LogIn className="h-4 w-4" /> 去登录
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

export default function NoPermissionPage() {
  return (
    <Suspense fallback={null}>
      <NoPermissionContent />
    </Suspense>
  );
}
