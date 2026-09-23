"use client";

/** 订单跟踪页的视觉组件:demo 与真实用户共用。hero 是品牌承诺文案;路线图与统计卡在真实视图由阶段驱动。 */
import { useTranslations } from "next-intl";
import { Anchor, Factory, Ship, Truck, Warehouse } from "lucide-react";

export type RouteStage = "CONFIRMED" | "LOADED" | "IN_TRANSIT" | "ARRIVED" | "CANCELLED";

/** 阶段 → 整体进度百分比(纯展示映射,不是履约给的数据)。 */
export const STAGE_PROGRESS: Record<RouteStage, number> = {
  CONFIRMED: 20,
  LOADED: 45,
  IN_TRANSIT: 75,
  ARRIVED: 100,
  CANCELLED: 0,
};

export function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-white p-4 flex items-center gap-3">
      <div className={`rounded-lg p-2.5 ${color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-navy">{value}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   路线可视化（CSS 绘制，不依赖地图 SDK）
   ═══════════════════════════════════════════════════════ */

/** 路线上的"当前节点"下标:demo 不传 stage 固定在海运;真实数据由阶段驱动。 */
const ROUTE_CURRENT_INDEX: Record<RouteStage, number> = {
  CONFIRMED: 1,   // 备货中:集货仓
  LOADED: 2,      // 已装柜:出发港
  IN_TRANSIT: 3,  // 海运
  ARRIVED: 4,     // 到达 Dar es Salaam
  CANCELLED: -1,  // 无进行中节点
};

export function RouteVisualization({ stage }: { stage?: RouteStage }) {
  const t = useTranslations("orderTracking");
  const current = stage === undefined ? 3 : ROUTE_CURRENT_INDEX[stage];
  const at = (i: number) => ({ done: i < current, current: i === current });

  const nodes = [
    { label: t("routeFactory"), sublabel: "China", icon: Factory, ...at(0) },
    { label: t("routeWarehouse"), sublabel: "Ningbo / Shanghai", icon: Warehouse, ...at(1) },
    { label: t("routePort"), sublabel: "China Port", icon: Anchor, ...at(2) },
    { label: t("routeSea"), sublabel: "~25 days", icon: Ship, ...at(3) },
    { label: "Dar es Salaam", sublabel: "Tanzania Port", icon: Anchor, ...at(4) },
    { label: t("routeDelivery"), sublabel: "Local", icon: Truck, ...at(5) },
  ];

  return (
    <div className="flex items-center justify-between gap-0 overflow-x-auto py-4">
      {nodes.map((node, i) => {
        const Icon = node.icon;
        const isLast = i === nodes.length - 1;

        return (
          <div key={i} className="flex items-center flex-1 min-w-0">
            {/* 节点 */}
            <div className="flex flex-col items-center gap-2 shrink-0">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-full border-2 ${
                  node.done
                    ? "border-teal-500 bg-teal-500 text-white"
                    : node.current
                    ? "border-teal-500 bg-white text-teal-700 ring-4 ring-teal-100 animate-pulse"
                    : "border-slate-200 bg-white text-slate-300"
                }`}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="text-center">
                <p className={`text-xs font-medium ${node.done || node.current ? "text-navy" : "text-slate-400"}`}>
                  {node.label}
                </p>
                <p className="text-[10px] text-muted">{node.sublabel}</p>
              </div>
            </div>

            {/* 连线 */}
            {!isLast && (
              <div className="flex-1 mx-1 h-0.5 min-w-[20px]">
                <div
                  className={`h-full ${
                    node.done ? "bg-teal-400" : "bg-slate-200"
                  }`}
                  style={node.current ? {
                    background: "repeating-linear-gradient(90deg, #14b8a6 0, #14b8a6 6px, transparent 6px, transparent 12px)",
                  } : undefined}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
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
        src="/images/fulfillment/hero-port.jpg"
        alt="Container port"
        className="absolute inset-0 w-full h-full object-cover"
      />
      {/* 渐变遮罩 — 左侧深色保证文字可读，右侧半透明露出照片 */}
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(to right, rgba(10,37,64,0.92) 0%, rgba(13,77,77,0.85) 45%, rgba(13,77,77,0.5) 70%, rgba(13,77,77,0.3) 100%)",
        }}
      />
      {/* 底部暖金色边线 */}
      <div className="absolute bottom-0 left-0 right-0 h-[3px]" style={{ background: "linear-gradient(90deg, #e3a615, #D4A853, transparent)" }} />

      <div className="relative flex items-center gap-8 px-8 py-10 md:py-12">
        {/* 左侧文案 */}
        <div className="flex-1 min-w-0 z-10">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 backdrop-blur-sm px-3 py-1 text-xs font-medium text-white/90">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" />
              {t("heroBadge")}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight drop-shadow-lg">
            {t("heroTitle")}
          </h1>
          <p className="mt-2.5 text-sm md:text-base text-white/75 leading-relaxed max-w-lg drop-shadow">
            {t("heroSubtitle")}
          </p>

          {/* 关键指标 */}
          <div className="mt-6 flex gap-8 flex-wrap">
            {[
              { value: "25-30", unit: t("heroDays"), label: t("heroTransitTime") },
              { value: "11", unit: t("heroSteps"), label: t("heroMilestones") },
              { value: "100%", unit: "", label: t("heroVisibility") },
            ].map((stat, i) => (
              <div key={i}>
                <p className="text-2xl md:text-3xl font-bold text-white drop-shadow-lg">
                  {stat.value}
                  {stat.unit && <span className="text-sm font-medium text-amber-300 ml-1">{stat.unit}</span>}
                </p>
                <p className="text-[11px] text-white/60 mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


