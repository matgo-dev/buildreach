"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldOff, ArrowLeft, LayoutDashboard, LogIn } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";

function NoPermissionContent() {
  const router = useRouter();
  const params = useSearchParams();
  const reason = params.get("reason"); // "role" | null
  const user = useAuthStore((s) => s.user);
  const t = useTranslations("noPermission");

  const homePath = user ? defaultDashboardOf(user.roles) : "/";

  // 根据拦截原因选择提示文案
  const hint = !user
    ? t("notLoggedIn")
    : reason === "role"
      ? t("reasonRole")
      : t("reasonPermission");

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="w-full max-w-md text-center">
        {/* 大图标 */}
        <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-slate-100">
          <ShieldOff className="h-12 w-12 text-slate-400" strokeWidth={1.5} />
        </div>

        {/* 标题 */}
        <h1 className="text-2xl font-bold text-slate-800">
          {t("title")}
        </h1>

        {/* 说明 */}
        <p className="mt-3 text-sm text-slate-500">
          {t("description")}
        </p>

        {/* 操作按钮 */}
        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={() => router.back()}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("goBack")}
          </button>

          {user ? (
            <Link
              href={homePath}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-800 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700"
            >
              <LayoutDashboard className="h-4 w-4" />
              {t("goDashboard")}
            </Link>
          ) : (
            <Link
              href="/login"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-800 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700"
            >
              <LogIn className="h-4 w-4" />
              {t("goLogin")}
            </Link>
          )}
        </div>
      </div>
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
