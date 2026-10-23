"use client";

import { useLocale, useTranslations } from "next-intl";
import useSWR from "swr";
import { AlertTriangle } from "lucide-react";

import { systemAlertsApi, type SystemAlertItem } from "@/lib/api/systemAlerts";
import { useAuthStore } from "@/stores/authStore";

const INTERNAL_ROLES = ["OPERATOR", "ADMIN"];

/**
 * 系统告警横幅 — 外部依赖(翻译服务等)挂掉时给内部账号看的红条。
 * 非空就显示,条件解除自动消失,不能手动关;买家/供应商不请求也不显示。
 */
export function SystemAlertBanner() {
  const user = useAuthStore((s) => s.user);
  const isInternal = user?.roles.some((r) => INTERNAL_ROLES.includes(r)) ?? false;
  const t = useTranslations("systemAlerts");
  const locale = useLocale();

  const { data } = useSWR(
    isInternal ? "/api/v1/operator/system-alerts" : null,
    () => systemAlertsApi.list(),
    { refreshInterval: 60_000, revalidateOnFocus: true },
  );
  const items: SystemAlertItem[] = data?.items ?? [];
  if (items.length === 0) return null;

  const fmtSince = (iso: string | null) =>
    iso ? new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short" }).format(new Date(iso)) : "";

  const text = (a: SystemAlertItem) => {
    if (a.kind === "translation_down") {
      return t("translationDown", {
        detail: a.detail ?? t("unknownError"),
        pending: a.pending_rows,
        since: fmtSince(a.since),
      });
    }
    return t("generic", { kind: a.kind, detail: a.detail ?? "", since: fmtSince(a.since) });
  };

  return (
    <div role="alert" className="shrink-0 bg-red-600 text-white text-sm">
      {items.map((a) => (
        <div key={a.kind} className="flex items-start gap-2 px-6 py-2">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span className="font-semibold">{t("prefix")}</span>
          <span>{text(a)}</span>
        </div>
      ))}
    </div>
  );
}
