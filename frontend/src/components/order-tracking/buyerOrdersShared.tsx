"use client";

import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Building2, Headset, Link2Off, Package, RefreshCw } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { formatDate } from "@/lib/formatters";
import {
  formatDecimalString,
  type BindingState,
  type CustomsStatus,
  type OrderStage,
  type PortalValueSegments,
  type ShipmentStage,
} from "@/lib/api/buyerOrders";
import { lookup, segmentShares, type SegmentKey } from "./orderProgress";

/** 订单级(整单事实六态)/ 柜级(递进链)阶段 → i18n key + 徽标配色。API 只给 code,标签在 messages。
 *  两套只在 ARRIVED 上同名且含义一致(全部到港 / 本柜到港),故一张表。 */
const STAGE_META: Record<OrderStage | ShipmentStage, { key: string; cls: string }> = {
  NOT_SHIPPED: { key: "stageNotShipped", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  PARTIALLY_SHIPPED: { key: "stagePartiallyShipped", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  SHIPPED: { key: "stageShipped", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  PARTIALLY_ARRIVED: { key: "stagePartiallyArrived", cls: "bg-teal-50 text-teal-700 border-teal-200" },
  LOADED: { key: "stageLoaded", cls: "bg-sky-50 text-sky-700 border-sky-200" },
  CLEARED: { key: "stageCleared", cls: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  IN_TRANSIT: { key: "stageInTransit", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  ARRIVED: { key: "stageArrived", cls: "bg-green-50 text-green-700 border-green-200" },
  CANCELLED: { key: "stageCancelled", cls: "bg-slate-100 text-muted border-slate-200" },
};

/** 履约端新增了前端不认识的 stage 时:灰底显示原始码,不冒充任何已知阶段。 */
const UNKNOWN_STAGE_CLS = "bg-slate-100 text-muted border-slate-200";

export function StagePill({ stage, size = "sm" }: { stage: OrderStage | string; size?: "sm" | "md" }) {
  const t = useTranslations("orderTracking");
  const meta = lookup(STAGE_META, stage);
  const pad = size === "md" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${pad} ${meta ? meta.cls : UNKNOWN_STAGE_CLS}`}>
      {meta ? t(meta.key) : stage}
    </span>
  );
}

/** 已知阶段的 i18n key;不认识的阶段 → null,由调用方显示原始码。 */
export function stageLabelKey(stage: string): string | null {
  return lookup(STAGE_META, stage)?.key ?? null;
}

/** 柜的报关状态徽标:未申报 / 申报中 / 已放行;不认识的值灰底显示原始码。 */
const CUSTOMS_META: Record<CustomsStatus, { key: string; cls: string }> = {
  NONE: { key: "customsNone", cls: "bg-slate-50 text-ink-2 border-slate-200" },
  DECLARED: { key: "customsDeclared", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  RELEASED: { key: "customsReleased", cls: "bg-green-50 text-green-700 border-green-200" },
};

export function CustomsPill({ status }: { status: CustomsStatus | string }) {
  const t = useTranslations("orderTracking");
  const meta = lookup(CUSTOMS_META, status);
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta ? meta.cls : UNKNOWN_STAGE_CLS}`}>
      {meta ? t(meta.key) : status}
    </span>
  );
}

/** 五段的 i18n key 与条色(最领先在前)。色阶:到港绿 → 海运蓝 → 装柜浅蓝 → 在仓琥珀 → 未到仓灰。 */
const SEGMENT_META: Record<SegmentKey, { key: string; bar: string; dot: string }> = {
  arrived: { key: "segArrived", bar: "bg-green-500", dot: "bg-green-500" },
  in_transit: { key: "segInTransit", bar: "bg-blue-500", dot: "bg-blue-500" },
  loaded: { key: "segLoaded", bar: "bg-sky-300", dot: "bg-sky-300" },
  in_warehouse: { key: "segInWarehouse", bar: "bg-amber-400", dot: "bg-amber-400" },
  not_received: { key: "segNotReceived", bar: "bg-slate-200", dot: "bg-slate-300" },
};

/**
 * 按货值的分段进度条(契约 §5.3 v5)。零宽段不画;`legend` 时下方列非零段的名称 + 百分比(详情头),
 * 否则只有细条(列表卡)。五段全零(取消单等)不渲染任何东西。
 */
export function ValueSegmentBar({ segments, legend = false }: { segments: PortalValueSegments; legend?: boolean }) {
  const t = useTranslations("orderTracking");
  const shares = segmentShares(segments).filter((s) => s.share > 0);
  if (shares.length === 0) return null;
  const pct = (share: number) => `${Math.round(share * 100)}%`;
  return (
    <div>
      <div
        className={`flex w-full overflow-hidden rounded-full bg-slate-100 ${legend ? "h-2.5" : "h-1.5"}`}
        role="img"
        aria-label={shares.map((s) => `${t(SEGMENT_META[s.key].key)} ${pct(s.share)}`).join(", ")}
      >
        {shares.map((s) => (
          <div key={s.key} className={`h-full ${SEGMENT_META[s.key].bar}`} style={{ width: `${s.share * 100}%` }} />
        ))}
      </div>
      {legend && (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {shares.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className={`inline-block h-2 w-2 rounded-full ${SEGMENT_META[s.key].dot}`} />
              {t(SEGMENT_META[s.key].key)}
              <span className="font-medium text-navy">{pct(s.share)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 关键日期行:最近一柜预计到港 · 共 N 柜;全部到港 → 共 N 柜 · 已全部到港;无柜 → 不显示。 */
export function KeyDateLine({ shipmentCount, nextEta, stage }: { shipmentCount: number; nextEta: string | null; stage: string }) {
  const t = useTranslations("orderTracking");
  const day = useDay();
  if (shipmentCount === 0) return null;
  if (nextEta) return <p className="text-sm text-navy">{t("nextEta", { date: day(nextEta), count: shipmentCount })}</p>;
  if (stage === "ARRIVED") return <p className="text-sm text-navy">{t("allArrived", { count: shipmentCount })}</p>;
  return <p className="text-sm text-muted">{t("containerCount", { count: shipmentCount })}</p>;
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
          className="inline-flex items-center gap-2 rounded-full mall-btn-primary px-6 py-2.5 text-sm font-medium transition-colors"
        >
          {t("bindingNoOrgAction")}
        </Link>
      )}
      {kind === "UNAVAILABLE" && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-full mall-btn-primary px-6 py-2.5 text-sm font-medium transition-colors"
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
        className="inline-flex items-center gap-2 rounded-full mall-btn-primary px-6 py-2.5 text-sm font-medium transition-colors"
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
