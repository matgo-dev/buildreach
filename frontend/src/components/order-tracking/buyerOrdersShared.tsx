"use client";

import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Building2, Headset, Link2Off, Package, RefreshCw } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { formatDate } from "@/lib/formatters";
import { formatDecimalString, type BindingState, type OrderStage } from "@/lib/api/buyerOrders";

/** 订单级 / 柜级阶段 → i18n key + 徽标配色。API 只给 code,标签在 messages。 */
const STAGE_META: Record<OrderStage, { key: string; cls: string }> = {
  CONFIRMED: { key: "stageConfirmed", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  LOADED: { key: "stageLoaded", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  IN_TRANSIT: { key: "stageInTransit", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  ARRIVED: { key: "stageArrived", cls: "bg-green-50 text-green-700 border-green-200" },
  CANCELLED: { key: "stageCancelled", cls: "bg-slate-100 text-slate-500 border-slate-200" },
};

export function StagePill({ stage, size = "sm" }: { stage: OrderStage; size?: "sm" | "md" }) {
  const t = useTranslations("orderTracking");
  const meta = STAGE_META[stage] ?? STAGE_META.CONFIRMED;
  const pad = size === "md" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${pad} ${meta.cls}`}>
      {t(meta.key)}
    </span>
  );
}

/** 金额:currency + decimal string,不经 float。 */
export function Money({ amount, currency, className = "" }: { amount: string; currency: string; className?: string }) {
  return (
    <span className={className}>
      <span className="text-xs text-muted mr-1">{currency}</span>
      {formatDecimalString(amount)}
    </span>
  );
}

/** 日期只显示到天;API 时间戳为 UTC,formatDate 会转本地时区。 */
export function useDay() {
  const locale = useLocale();
  return (iso: string | null | undefined) =>
    iso ? formatDate(iso, locale, { hour: undefined, minute: undefined }) : "—";
}

export function useDayTime() {
  const locale = useLocale();
  return (iso: string | null | undefined) => (iso ? formatDate(iso, locale) : "—");
}

/** 页头(真实用户不展示营销 hero)。 */
export function PageHeader() {
  const t = useTranslations("orderTracking");
  return (
    <div>
      <h1 className="text-2xl font-bold text-navy">{t("pageTitle")}</h1>
      <p className="mt-1 text-sm text-muted">{t("pageSubtitle")}</p>
    </div>
  );
}

/** 四态 + 不可用的整幅提示面板。 */
export function StatePanel({
  kind,
  onRetry,
}: {
  kind: BindingState | "UNAVAILABLE";
  onRetry?: () => void;
}) {
  const t = useTranslations("orderTracking");
  const meta = {
    NO_ORG: { icon: Building2, title: "bindingNoOrgTitle", desc: "bindingNoOrgDesc" },
    AMBIGUOUS_ORG: { icon: Headset, title: "bindingAmbiguousTitle", desc: "bindingAmbiguousDesc" },
    ORG_DISABLED: { icon: Headset, title: "bindingDisabledTitle", desc: "bindingDisabledDesc" },
    NOT_BOUND: { icon: Link2Off, title: "bindingNotBoundTitle", desc: "bindingNotBoundDesc" },
    UNAVAILABLE: { icon: AlertCircle, title: "unavailableTitle", desc: "unavailableDesc" },
  }[kind];
  const Icon = meta.icon;

  return (
    <div className="rounded-xl border border-line bg-white p-10 md:p-16 text-center">
      <Icon className="h-12 w-12 text-slate-300 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-navy mb-2">{t(meta.title)}</h3>
      <p className="text-sm text-muted mb-5 max-w-md mx-auto">{t(meta.desc)}</p>
      {kind === "NO_ORG" && (
        <Link
          href="/account"
          className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-6 py-2.5 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
        >
          {t("bindingNoOrgAction")}
        </Link>
      )}
      {kind === "UNAVAILABLE" && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-6 py-2.5 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          {t("retry")}
        </button>
      )}
    </div>
  );
}

/** 空态:demo 与真实用户共用。 */
export function EmptyOrdersState() {
  const t = useTranslations("orderTracking");
  return (
    <div className="rounded-xl border border-line bg-white p-16 text-center">
      <Package className="h-12 w-12 text-slate-300 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-navy mb-2">{t("emptyTitle")}</h3>
      <p className="text-sm text-muted mb-5">{t("emptyDesc")}</p>
      <Link
        href="/mall"
        className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-6 py-2.5 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
      >
        {t("emptyBrowse")}
      </Link>
    </div>
  );
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-xl border border-line bg-white p-5 animate-pulse">
          <div className="h-4 w-40 rounded bg-slate-100" />
          <div className="mt-3 h-3 w-64 rounded bg-slate-100" />
          <div className="mt-2 h-3 w-24 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
