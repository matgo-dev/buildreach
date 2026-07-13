"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Package,
  Ship,
  FileText,
  ChevronRight,
  Clock,
  MapPin,
  CheckCircle2,
  Circle,
  Truck,
  ArrowLeft,
  Download,
  Container,
  Anchor,
  ClipboardCheck,
  Factory,
  Warehouse,
  ShieldCheck,
  PackageCheck,
  FileCheck,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { MOCK_ORDERS, type MockOrder, type Shipment, type Milestone, MILESTONE_KEYS } from "./mockOrders";


// 节点图标映射
const MILESTONE_ICONS: Record<string, React.ElementType> = {
  msOrderConfirmed: CheckCircle2,
  msSupplierPrep: Factory,
  msQualityInspection: ShieldCheck,
  msWarehouseReceipt: Warehouse,
  msConsolidation: Container,
  msCustomsExport: FileCheck,
  msSeaFreight: Ship,
  msPortArrival: Anchor,
  msCustomsImport: ClipboardCheck,
  msLocalDelivery: Truck,
  msDelivered: PackageCheck,
};

/** 订单追踪页 — demo 用户看 mock 数据，真实用户看空状态 */
export function OrderTrackingPage() {
  const t = useTranslations("orderTracking");
  const user = useAuthStore((s) => s.user);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const isDemo = user?.is_demo ?? false;
  // TODO: 后续接真实 API 后，真实用户从后端拉订单数据
  const orders = isDemo ? MOCK_ORDERS : [];

  const selectedOrder = orders.find((o) => o.id === selectedId);

  if (selectedOrder) {
    return <OrderDetail order={selectedOrder} onBack={() => setSelectedId(null)} />;
  }

  return <OrderList orders={orders} onSelect={setSelectedId} />;
}

/* ═══════════════════════════════════════════════════════
   订单列表
   ═══════════════════════════════════════════════════════ */

function OrderList({
  orders,
  onSelect,
}: {
  orders: MockOrder[];
  onSelect: (id: string) => void;
}) {
  const t = useTranslations("orderTracking");

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <FulfillmentHeroBanner />

      {/* 状态统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Package} label={t("statTotal")} value={String(orders.length)} color="text-teal-700 bg-teal-50" />
        <StatCard icon={Ship} label={t("statInTransit")} value={String(orders.filter(o => o.statusKey === "statusInTransit").length)} color="text-blue-700 bg-blue-50" />
        <StatCard icon={Clock} label={t("statClearance")} value={String(orders.filter(o => o.statusKey === "statusCustomsClearance").length)} color="text-amber-700 bg-amber-50" />
        <StatCard icon={CheckCircle2} label={t("statDelivered")} value={String(orders.filter(o => o.statusKey === "statusDelivered").length)} color="text-green-700 bg-green-50" />
      </div>

      {/* 订单卡片列表 / 空状态 */}
      {orders.length > 0 ? (
        <div className="space-y-4">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} onClick={() => onSelect(order.id)} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-line bg-white p-16 text-center">
          <Package className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-navy mb-2">{t("emptyTitle")}</h3>
          <p className="text-sm text-muted mb-5">{t("emptyDesc")}</p>
          <a
            href="/mall"
            className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-6 py-2.5 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
          >
            {t("emptyBrowse")}
          </a>
        </div>
      )}
    </div>
  );
}

function StatCard({
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

function OrderCard({ order, onClick }: { order: MockOrder; onClick: () => void }) {
  const t = useTranslations("orderTracking");

  // 计算 ETA 倒计时
  const daysLeft = Math.max(0, Math.ceil((new Date(order.eta).getTime() - Date.now()) / 86_400_000));

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl border border-line bg-white p-5 hover:shadow-md hover:border-teal-200 transition-all group"
    >
      <div className="flex items-start justify-between gap-4">
        {/* 左侧：订单信息 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-sm font-semibold text-navy">{order.orderNo}</span>
            <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${order.statusColor}`}>
              {t(order.statusKey)}
            </span>
          </div>

          <div className="mt-2.5 flex items-center gap-4 text-sm text-muted flex-wrap">
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" />
              {order.buyerCompany}
            </span>
            <span>{t("orderDate")}: {order.createdAt}</span>
          </div>

          {/* 进度条 */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-muted mb-1.5">
              <span>{t(order.currentMilestoneKey)}</span>
              {order.progress < 100 && (
                <span className="flex items-center gap-1 text-teal-700 font-medium">
                  <Clock className="h-3 w-3" />
                  ETA: {order.eta} ({daysLeft} {t("daysLeft")})
                </span>
              )}
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400 transition-all"
                style={{ width: `${order.progress}%` }}
              />
            </div>
          </div>

          {/* 商品缩略 */}
          <div className="mt-3 flex items-center gap-2">
            <div className="flex -space-x-2">
              {order.items.slice(0, 4).map((item, i) => (
                <img
                  key={i}
                  src={item.image}
                  alt={item.nameEn}
                  className="h-8 w-8 rounded-md border-2 border-white object-cover"
                />
              ))}
              {order.items.length > 4 && (
                <span className="flex h-8 w-8 items-center justify-center rounded-md border-2 border-white bg-slate-100 text-[10px] font-medium text-muted">
                  +{order.items.length - 4}
                </span>
              )}
            </div>
            <span className="text-xs text-muted">
              {order.items.length} {t("itemCount")} · {order.shipments.length} {t("shipmentCount")}
            </span>
          </div>
        </div>

        {/* 右侧箭头 */}
        <ChevronRight className="h-5 w-5 text-muted group-hover:text-teal-700 shrink-0 mt-2 transition-colors" />
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════
   订单详情
   ═══════════════════════════════════════════════════════ */

function OrderDetail({ order, onBack }: { order: MockOrder; onBack: () => void }) {
  const t = useTranslations("orderTracking");
  const [activeShipment, setActiveShipment] = useState(0);

  const daysLeft = Math.max(0, Math.ceil((new Date(order.eta).getTime() - Date.now()) / 86_400_000));

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-muted hover:text-teal-700 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("backToList")}
      </button>

      {/* 顶部概览卡 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div
          className="px-6 py-5"
          style={{ background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 50%, #f0f9ff 100%)" }}
        >
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-navy">{order.orderNo}</h2>
                <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${order.statusColor}`}>
                  {t(order.statusKey)}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-4 text-sm text-muted flex-wrap">
                <span>{t("orderDate")}: {order.createdAt}</span>
                <span>{t("buyer")}: {order.buyerCompany}</span>
              </div>
            </div>
            {order.progress < 100 && (
              <div className="text-right">
                <p className="text-sm text-teal-700 font-medium flex items-center gap-1 justify-end">
                  <Clock className="h-3.5 w-3.5" />
                  ETA: {order.eta} ({daysLeft} {t("daysLeft")})
                </p>
              </div>
            )}
          </div>

          {/* 整体进度条 */}
          <div className="mt-4">
            <div className="h-2.5 rounded-full bg-white/60 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal-600 to-teal-400 transition-all"
                style={{ width: `${order.progress}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-muted">{t("overallProgress")}: {order.progress}%</p>
          </div>
        </div>
      </div>

      {/* 物流追踪 — 分包 Tab + Timeline */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <Ship className="h-5 w-5 text-teal-700" />
            {t("shipmentTracking")}
          </h3>
        </div>

        {/* 分包 Tab */}
        {order.shipments.length > 1 && (
          <div className="px-6 pt-3 flex gap-2 border-b border-line">
            {order.shipments.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setActiveShipment(i)}
                className={`px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
                  i === activeShipment
                    ? "border-teal-700 text-teal-700 bg-teal-50"
                    : "border-transparent text-muted hover:text-navy"
                }`}
              >
                {s.label}
                <span className="ml-2 text-xs text-muted">({s.containerType})</span>
              </button>
            ))}
          </div>
        )}

        {/* 物流信息 + 时间线 */}
        <ShipmentTimeline shipment={order.shipments[activeShipment]} />
      </div>

      {/* 商品明细 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <Package className="h-5 w-5 text-teal-700" />
            {t("orderItems")}
            <span className="text-sm font-normal text-muted">({order.items.length} {t("itemCount")})</span>
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="px-6 py-3 font-medium text-muted">{t("colProduct")}</th>
                <th className="px-4 py-3 font-medium text-muted">{t("colSku")}</th>
                <th className="px-4 py-3 font-medium text-muted text-right">{t("colQty")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {order.items.map((item, i) => (
                <tr key={i} className="hover:bg-slate-50/50">
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-3">
                      <img
                        src={item.image}
                        alt={item.nameEn}
                        className="h-10 w-10 rounded-lg object-cover border border-slate-100"
                      />
                      <div>
                        <p className="font-medium text-navy">{item.nameEn}</p>
                        <p className="text-xs text-muted">{item.name}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted">{item.sku}</td>
                  <td className="px-4 py-3 text-right text-navy">
                    {item.qty.toLocaleString()} {item.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 单据中心 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <FileText className="h-5 w-5 text-teal-700" />
            {t("documentCenter")}
          </h3>
        </div>
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {order.documents.map((doc, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-line p-3 hover:border-teal-200 hover:bg-teal-50/30 transition-colors cursor-pointer"
            >
              <div className="rounded-lg bg-teal-50 p-2 text-teal-700">
                <FileText className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-navy truncate">{doc.name}</p>
                <p className="text-xs text-muted">{doc.type} · {doc.date}</p>
              </div>
              <Download className="h-4 w-4 text-muted shrink-0" />
            </div>
          ))}
        </div>
      </div>

      {/* 路线示意 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <MapPin className="h-5 w-5 text-teal-700" />
            {t("routeMap")}
          </h3>
        </div>
        <div className="p-6">
          <RouteVisualization />
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   物流时间线
   ═══════════════════════════════════════════════════════ */

function ShipmentTimeline({ shipment }: { shipment: Shipment }) {
  const t = useTranslations("orderTracking");

  return (
    <div className="p-6">
      {/* 物流信息摘要 */}
      <div className="flex items-center gap-6 mb-6 text-sm flex-wrap">
        <div className="flex items-center gap-2">
          <Ship className="h-4 w-4 text-teal-700" />
          <span className="text-muted">{t("carrier")}:</span>
          <span className="font-medium text-navy">{shipment.carrier}</span>
        </div>
        <div className="flex items-center gap-2">
          <Package className="h-4 w-4 text-teal-700" />
          <span className="text-muted">{t("trackingNo")}:</span>
          <span className="font-mono font-medium text-navy">{shipment.trackingNo}</span>
        </div>
        <div className="flex items-center gap-2">
          <Container className="h-4 w-4 text-teal-700" />
          <span className="text-muted">{t("containerType")}:</span>
          <span className="font-medium text-navy">{shipment.containerType}</span>
        </div>
      </div>

      {/* 垂直时间线 */}
      <div className="relative">
        {shipment.milestones.map((ms, i) => {
          const Icon = MILESTONE_ICONS[ms.labelKey] || Circle;
          const isLast = i === shipment.milestones.length - 1;

          return (
            <div key={ms.id} className="relative flex gap-4 pb-6">
              {/* 左侧竖线 + 图标 */}
              <div className="relative flex flex-col items-center">
                <div
                  className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 ${
                    ms.status === "done"
                      ? "border-teal-500 bg-teal-500 text-white"
                      : ms.status === "current"
                      ? "border-teal-500 bg-white text-teal-700 ring-4 ring-teal-100"
                      : "border-slate-200 bg-white text-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                {!isLast && (
                  <div
                    className={`absolute top-9 w-0.5 ${
                      ms.status === "done" ? "bg-teal-400" : "bg-slate-200"
                    }`}
                    style={{ height: "calc(100% - 12px)" }}
                  />
                )}
              </div>

              {/* 右侧内容 */}
              <div className="flex-1 pt-1.5">
                <div className="flex items-center gap-3">
                  <span
                    className={`text-sm font-semibold ${
                      ms.status === "done"
                        ? "text-navy"
                        : ms.status === "current"
                        ? "text-teal-700"
                        : "text-slate-400"
                    }`}
                  >
                    {t(ms.labelKey)}
                  </span>
                  {ms.status === "current" && (
                    <span className="inline-flex items-center rounded-full bg-teal-100 border border-teal-200 px-2 py-0.5 text-[11px] font-medium text-teal-700">
                      {t("currentStep")}
                    </span>
                  )}
                </div>
                {ms.date && (
                  <p className="mt-0.5 text-xs text-muted">{ms.date}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   路线可视化（CSS 绘制，不依赖地图 SDK）
   ═══════════════════════════════════════════════════════ */

function RouteVisualization() {
  const t = useTranslations("orderTracking");

  const nodes = [
    { label: t("routeFactory"), sublabel: "China", icon: Factory, done: true },
    { label: t("routeWarehouse"), sublabel: "Ningbo / Shanghai", icon: Warehouse, done: true },
    { label: t("routePort"), sublabel: "China Port", icon: Anchor, done: true },
    { label: t("routeSea"), sublabel: "~25 days", icon: Ship, done: false, current: true },
    { label: "Dar es Salaam", sublabel: "Tanzania Port", icon: Anchor, done: false },
    { label: t("routeDelivery"), sublabel: "Local", icon: Truck, done: false },
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

function FulfillmentHeroBanner() {
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

