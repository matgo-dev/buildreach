"use client";

/** 订单跟踪页的视觉组件:demo 与真实用户共用。hero 是品牌承诺文案;统计卡可点击下钻。
 *  (v5 删掉了「运输路线」横条:与时间线、订单头分段条三处重复,多柜时按订单级定位与按柜时间线矛盾。) */
import { useTranslations } from "next-intl";
import { FULFILLMENT_NODES } from "./orderProgress";

/** 统计卡。传 onClick 即可点击下钻,active 标当前筛选。 */
export function StatCard({
  icon: Icon,
  label,
  value,
  color,
  onClick,
  active = false,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color: string;
  onClick?: () => void;
  active?: boolean;
}) {
  const inner = (
    <>
      <div className={`rounded-lg p-2.5 ${color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-navy">{value}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </>
  );
  const base = "rounded-xl border bg-white p-4 flex items-center gap-3 text-left";
  if (!onClick) return <div className={`${base} border-line`}>{inner}</div>;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`${base} w-full transition-colors ${
        active ? "border-teal-600 ring-2 ring-teal-100" : "border-line hover:border-teal-300"
      }`}
    >
      {inner}
    </button>
  );
}


/* ═══════════════════════════════════════════════════════
   Hero Banner — 海运物流插画 + 文案
   ═══════════════════════════════════════════════════════ */

export function FulfillmentHeroBanner() {
  const t = useTranslations("orderTracking");

  return (
    <div className="relative overflow-hidden rounded-2xl min-h-[260px]">
      {/* 真实港口照片背景 */}
      <img
        src="/images/fulfillment/hero-port-day.jpg"
        alt="Container port"
        className="absolute inset-0 w-full h-full object-cover object-[center_70%]"
      />
      {/* 浅色遮罩 — 左侧雾白托住深绿字，右侧淡出露出港口（与其他内页浅色头部一致） */}
      <div className="absolute inset-0 bg-gradient-to-r from-bg/95 via-teal-50/70 via-35% to-transparent to-60%" />
      {/* 底部柠绿细线 */}
      <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-lime" />

      <div className="relative flex items-center gap-8 px-8 py-10 md:py-12">
        {/* 左侧文案 */}
        <div className="flex-1 min-w-0 z-10">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-900/10 bg-white/70 backdrop-blur-sm px-3 py-1 text-xs font-medium text-teal-900">
              <span className="h-1.5 w-1.5 rounded-full bg-lime animate-pulse" />
              {t("heroBadge")}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-teal-900 leading-tight max-w-md break-keep">
            {t("heroTitle")}
          </h1>
          <p className="mt-2.5 text-sm md:text-base text-ink-2 leading-relaxed max-w-md">
            {t("heroSubtitle")}
          </p>

          {/* 关键指标 */}
          <div className="mt-6 flex gap-8 flex-wrap">
            {[
              { value: "25-30", unit: t("heroDays"), label: t("heroTransitTime") },
              { value: String(FULFILLMENT_NODES.length), unit: t("heroSteps"), label: t("heroMilestones") },
              { value: "100%", unit: "", label: t("heroVisibility") },
            ].map((stat, i) => (
              <div key={i}>
                <p className="text-2xl md:text-3xl font-bold text-teal-900">
                  {stat.value}
                  {stat.unit && <span className="text-sm font-medium text-teal-600 ml-1">{stat.unit}</span>}
                </p>
                <p className="text-[11px] text-muted mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


