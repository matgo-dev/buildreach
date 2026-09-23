"use client";

import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Building2, Headset, Link2Off, Package, RefreshCw } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { formatDate } from "@/lib/formatters";
import { formatDecimalString, type BindingState, type CustomsStatus, type OrderStage } from "@/lib/api/buyerOrders";

/** 订单级 / 柜级阶段 → i18n key + 徽标配色。API 只给 code,标签在 messages。 */
const STAGE_META: Record<OrderStage, { key: string; cls: string }> = {
  CONFIRMED: { key: "stageConfirmed", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  RECEIVED: { key: "stageReceived", cls: "bg-orange-50 text-orange-700 border-orange-200" },
  LOADED: { key: "stageLoaded", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  CLEARED: { key: "stageCleared", cls: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  IN_TRANSIT: { key: "stageInTransit", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  ARRIVED: { key: "stageArrived", cls: "bg-green-50 text-green-700 border-green-200" },
  CANCELLED: { key: "stageCancelled", cls: "bg-slate-100 text-slate-500 border-slate-200" },
};

/** 履约端新增了前端不认识的 stage 时:灰底显示原始码,不冒充任何已知阶段。 */
const UNKNOWN_STAGE_CLS = "bg-slate-100 text-slate-500 border-slate-200";

export function StagePill({ stage, size = "sm" }: { stage: OrderStage | string; size?: "sm" | "md" }) {
  const t = useTranslations("orderTracking");
  const meta = STAGE_META[stage as OrderStage];
  const pad = size === "md" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${pad} ${meta ? meta.cls : UNKNOWN_STAGE_CLS}`}>
      {meta ? t(meta.key) : stage}
    </span>
  );
}

/** 已知阶段的 i18n key;不认识的阶段 → null,由调用方显示原始码。 */
export function stageLabelKey(stage: string): string | null {
  return Object.prototype.hasOwnProperty.call(STAGE_META, stage) ? STAGE_META[stage as OrderStage].key : null;
}

/** 柜的报关状态徽标:未申报 / 申报中 / 已放行;不认识的值灰底显示原始码。 */
const CUSTOMS_META: Record<CustomsStatus, { key: string; cls: string }> = {
  NONE: { key: "customsNone", cls: "bg-slate-50 text-slate-600 border-slate-200" },
  DECLARED: { key: "customsDeclared", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  RELEASED: { key: "customsReleased", cls: "bg-green-50 text-green-700 border-green-200" },
};

export function CustomsPill({ status }: { status: CustomsStatus | string }) {
  const t = useTranslations("orderTracking");
  const meta = Object.prototype.hasOwnProperty.call(CUSTOMS_META, status) ? CUSTOMS_META[status as CustomsStatus] : null;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta ? meta.cls : UNKNOWN_STAGE_CLS}`}>
      {meta ? t(meta.key) : status}
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

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** 履约的 etd/atd/eta/里程碑是纯日期(YYYY-MM-DD),不能当 UTC 时刻转本地时区(会跨天);
 *  loaded_at/created_at 是 UTC 时间戳,走 formatDate 转本地。 */
function formatDateOnly(value: string, locale: string): string {
  const [y, m, d] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date(y, m - 1, d));
}

/** 只显示到天。 */
export function useDay() {
  const locale = useLocale();
  return (v: string | null | undefined) => {
    if (!v) return "—";
    if (DATE_ONLY.test(v)) return formatDateOnly(v, locale);
    return formatDate(v, locale, { hour: undefined, minute: undefined });
  };
}

/** 有时刻显示到分,纯日期只显示日。 */
export function useDayTime() {
  const locale = useLocale();
  return (v: string | null | undefined) => {
    if (!v) return "—";
    if (DATE_ONLY.test(v)) return formatDateOnly(v, locale);
    return formatDate(v, locale);
  };
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
