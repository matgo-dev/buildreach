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

/** 订单追踪页 — 列表 + 详情双视图 */
export function OrderTrackingPage() {
  const t = useTranslations("orderTracking");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedOrder = MOCK_ORDERS.find((o) => o.id === selectedId);

  if (selectedOrder) {
    return <OrderDetail order={selectedOrder} onBack={() => setSelectedId(null)} />;
  }

  return <OrderList orders={MOCK_ORDERS} onSelect={setSelectedId} />;
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
        <StatCard icon={Package} label={t("statTotal")} value="3" color="text-teal-700 bg-teal-50" />
        <StatCard icon={Ship} label={t("statInTransit")} value="1" color="text-blue-700 bg-blue-50" />
        <StatCard icon={Clock} label={t("statClearance")} value="1" color="text-amber-700 bg-amber-50" />
        <StatCard icon={CheckCircle2} label={t("statDelivered")} value="1" color="text-green-700 bg-green-50" />
      </div>

      {/* 订单卡片列表 */}
      <div className="space-y-4">
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} onClick={() => onSelect(order.id)} />
        ))}
      </div>
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
    <div
      className="relative overflow-hidden rounded-2xl"
      style={{
        background: "linear-gradient(135deg, #0A2540 0%, #0D4D4D 35%, #1A6B6B 60%, #0D4D4D 100%)",
      }}
    >
      {/* 背景装饰：网格 + 光晕 */}
      <div className="absolute inset-0 opacity-[0.07]" style={{
        backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
        backgroundSize: "32px 32px",
      }} />
      <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full opacity-10"
        style={{ background: "radial-gradient(circle, #2A9D9D 0%, transparent 70%)" }} />
      <div className="absolute bottom-0 left-1/4 w-[300px] h-[300px] rounded-full opacity-[0.06]"
        style={{ background: "radial-gradient(circle, #D4A853 0%, transparent 70%)" }} />

      <div className="relative flex items-center gap-8 px-8 py-8 md:py-10">
        {/* 左侧文案 */}
        <div className="flex-1 min-w-0 z-10">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-400/30 bg-teal-400/10 px-3 py-1 text-xs font-medium text-teal-300">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" />
              {t("heroBadge")}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight">
            {t("heroTitle")}
          </h1>
          <p className="mt-2.5 text-sm md:text-base text-teal-200/80 leading-relaxed max-w-lg">
            {t("heroSubtitle")}
          </p>

          {/* 关键指标 */}
          <div className="mt-5 flex gap-6 flex-wrap">
            {[
              { value: "25-30", unit: t("heroDays"), label: t("heroTransitTime") },
              { value: "11", unit: t("heroSteps"), label: t("heroMilestones") },
              { value: "100%", unit: "", label: t("heroVisibility") },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <p className="text-xl md:text-2xl font-bold text-white">
                  {stat.value}
                  {stat.unit && <span className="text-sm font-normal text-teal-300 ml-1">{stat.unit}</span>}
                </p>
                <p className="text-[11px] text-teal-300/70">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* 右侧 SVG 插画 — 海运场景 */}
        <div className="hidden md:block w-[380px] shrink-0">
          <ShippingIllustration />
        </div>
      </div>
    </div>
  );
}

/** 海运场景 SVG 插画 — 集装箱船 + 港口起重机 + 海浪 + 航线 */
function ShippingIllustration() {
  return (
    <svg viewBox="0 0 400 260" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-auto">
      {/* 天空渐变 */}
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0D4D4D" stopOpacity="0" />
          <stop offset="100%" stopColor="#1A6B6B" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id="ocean" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0e5e6b" />
          <stop offset="100%" stopColor="#062a30" />
        </linearGradient>
        <linearGradient id="ship-hull" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a3a5c" />
          <stop offset="100%" stopColor="#0f2440" />
        </linearGradient>
        <linearGradient id="gold-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#e3a615" />
          <stop offset="100%" stopColor="#D4A853" />
        </linearGradient>
        <linearGradient id="container1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#e74c3c" />
          <stop offset="100%" stopColor="#c0392b" />
        </linearGradient>
        <linearGradient id="container2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3498db" />
          <stop offset="100%" stopColor="#2980b9" />
        </linearGradient>
        <linearGradient id="container3" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2ecc71" />
          <stop offset="100%" stopColor="#27ae60" />
        </linearGradient>
        <linearGradient id="container4" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f39c12" />
          <stop offset="100%" stopColor="#e67e22" />
        </linearGradient>
        {/* 航线虚线动画 */}
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* 海面 */}
      <rect x="0" y="155" width="400" height="105" fill="url(#ocean)" />

      {/* 海浪 — 三层，不同速度 */}
      <g opacity="0.4">
        <path d="M0 170 Q20 162 40 170 Q60 178 80 170 Q100 162 120 170 Q140 178 160 170 Q180 162 200 170 Q220 178 240 170 Q260 162 280 170 Q300 178 320 170 Q340 162 360 170 Q380 178 400 170" stroke="#3DB8B8" strokeWidth="1.5" fill="none">
          <animateTransform attributeName="transform" type="translate" values="0,0;-40,0;0,0" dur="6s" repeatCount="indefinite" />
        </path>
      </g>
      <g opacity="0.25">
        <path d="M0 180 Q25 173 50 180 Q75 187 100 180 Q125 173 150 180 Q175 187 200 180 Q225 173 250 180 Q275 187 300 180 Q325 173 350 180 Q375 187 400 180" stroke="#6FD1D1" strokeWidth="1" fill="none">
          <animateTransform attributeName="transform" type="translate" values="0,0;30,0;0,0" dur="8s" repeatCount="indefinite" />
        </path>
      </g>
      <g opacity="0.15">
        <path d="M0 195 Q30 189 60 195 Q90 201 120 195 Q150 189 180 195 Q210 201 240 195 Q270 189 300 195 Q330 201 360 195 Q390 189 400 195" stroke="#A1E3E3" strokeWidth="0.8" fill="none">
          <animateTransform attributeName="transform" type="translate" values="0,0;-20,0;0,0" dur="10s" repeatCount="indefinite" />
        </path>
      </g>

      {/* 远景：月亮/太阳 */}
      <circle cx="340" cy="50" r="22" fill="#D4A853" opacity="0.15" />
      <circle cx="340" cy="50" r="18" fill="#e3a615" opacity="0.08" />

      {/* 远景：小云朵 */}
      <g opacity="0.12" fill="white">
        <ellipse cx="60" cy="40" rx="30" ry="8" />
        <ellipse cx="50" cy="36" rx="18" ry="7" />
        <ellipse cx="75" cy="37" rx="16" ry="6" />
      </g>
      <g opacity="0.08" fill="white">
        <ellipse cx="280" cy="30" rx="24" ry="6" />
        <ellipse cx="268" cy="27" rx="14" ry="5" />
      </g>

      {/* ── 港口起重机（左侧） ── */}
      <g transform="translate(20, 90)">
        {/* 支柱 */}
        <rect x="8" y="20" width="5" height="66" fill="#3a5068" />
        <rect x="25" y="20" width="5" height="66" fill="#3a5068" />
        {/* 横梁 */}
        <rect x="0" y="15" width="60" height="5" rx="1" fill="#4a6078" />
        {/* 吊臂 */}
        <rect x="28" y="0" width="3" height="20" fill="#4a6078" />
        <rect x="15" y="0" width="20" height="3" fill="#D4A853" />
        {/* 吊钩 */}
        <line x1="18" y1="3" x2="18" y2="18" stroke="#D4A853" strokeWidth="1" />
        <rect x="14" y="18" width="8" height="5" rx="1" fill="#e3a615" />
        {/* 底座 */}
        <rect x="2" y="86" width="34" height="4" rx="1" fill="#2a3a50" />
      </g>

      {/* ── 集装箱船（中央主体） ── */}
      <g transform="translate(100, 95)">
        <animateTransform attributeName="transform" type="translate" values="100,95;100,98;100,95" dur="4s" repeatCount="indefinite" />

        {/* 船体 */}
        <path d="M0 55 L15 70 L185 70 L200 55 L195 40 L5 40 Z" fill="url(#ship-hull)" />
        {/* 水线 */}
        <path d="M15 62 L185 62" stroke="#c0392b" strokeWidth="2.5" opacity="0.7" />
        {/* 甲板 */}
        <rect x="10" y="35" width="180" height="8" rx="1" fill="#2a4a6a" />

        {/* 集装箱 — 第一层 */}
        <rect x="25" y="12" width="28" height="22" rx="1.5" fill="url(#container1)" />
        <rect x="56" y="12" width="28" height="22" rx="1.5" fill="url(#container2)" />
        <rect x="87" y="12" width="28" height="22" rx="1.5" fill="url(#container3)" />
        <rect x="118" y="12" width="28" height="22" rx="1.5" fill="url(#container4)" />
        <rect x="149" y="12" width="28" height="22" rx="1.5" fill="url(#container1)" />

        {/* 集装箱 — 第二层 */}
        <rect x="40" y="-10" width="28" height="20" rx="1.5" fill="url(#container3)" />
        <rect x="71" y="-10" width="28" height="20" rx="1.5" fill="url(#container4)" />
        <rect x="102" y="-10" width="28" height="20" rx="1.5" fill="url(#container2)" />
        <rect x="133" y="-10" width="28" height="20" rx="1.5" fill="url(#container1)" />

        {/* 集装箱纹理线 */}
        {[25, 56, 87, 118, 149].map((x) => (
          <line key={x} x1={x + 14} y1="14" x2={x + 14} y2="32" stroke="rgba(0,0,0,0.15)" strokeWidth="0.5" />
        ))}

        {/* 驾驶舱 */}
        <rect x="160" y="-22" width="22" height="30" rx="2" fill="#1a3a5c" />
        <rect x="163" y="-18" width="16" height="10" rx="1" fill="#3DB8B8" opacity="0.5" />
        {/* 烟囱 */}
        <rect x="167" y="-32" width="8" height="12" rx="1" fill="#2a4a6a" />
        <rect x="167" y="-32" width="8" height="3" rx="1" fill="#D4A853" />
        {/* 烟雾 */}
        <g opacity="0.15">
          <circle cx="171" cy="-38" r="3" fill="white">
            <animate attributeName="cy" values="-38;-52;-38" dur="3s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.2;0;0.2" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="174" cy="-42" r="2" fill="white">
            <animate attributeName="cy" values="-42;-55;-42" dur="3.5s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.15;0;0.15" dur="3.5s" repeatCount="indefinite" />
          </circle>
        </g>

        {/* 船头浪花 */}
        <g opacity="0.35">
          <path d="M-5 58 Q-15 52 -8 46" stroke="white" strokeWidth="1.5" fill="none" />
          <path d="M-2 62 Q-12 58 -6 52" stroke="white" strokeWidth="1" fill="none" />
        </g>
      </g>

      {/* ── 航线标记 ── */}
      <g filter="url(#glow)">
        <path d="M50 220 Q130 200 200 210 Q280 220 370 215" stroke="#D4A853" strokeWidth="1.5" strokeDasharray="8 4" fill="none" opacity="0.6">
          <animate attributeName="stroke-dashoffset" values="0;-24" dur="2s" repeatCount="indefinite" />
        </path>
      </g>

      {/* 航线节点：中国 */}
      <g transform="translate(40, 215)">
        <circle cx="0" cy="0" r="5" fill="#D4A853" />
        <circle cx="0" cy="0" r="8" fill="none" stroke="#D4A853" strokeWidth="1" opacity="0.4">
          <animate attributeName="r" values="8;14;8" dur="2s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.4;0;0.4" dur="2s" repeatCount="indefinite" />
        </circle>
        <text x="0" y="16" textAnchor="middle" fill="#D4A853" fontSize="9" fontWeight="600">CHINA</text>
      </g>

      {/* 航线节点：达累斯萨拉姆 */}
      <g transform="translate(370, 210)">
        <circle cx="0" cy="0" r="5" fill="#3DB8B8" />
        <circle cx="0" cy="0" r="8" fill="none" stroke="#3DB8B8" strokeWidth="1" opacity="0.4">
          <animate attributeName="r" values="8;14;8" dur="2.5s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.4;0;0.4" dur="2.5s" repeatCount="indefinite" />
        </circle>
        <text x="0" y="16" textAnchor="middle" fill="#3DB8B8" fontSize="8" fontWeight="600">DAR ES SALAAM</text>
      </g>

      {/* 移动中的货物小点 */}
      <circle r="3" fill="#e3a615">
        <animateMotion dur="5s" repeatCount="indefinite" path="M50 220 Q130 200 200 210 Q280 220 370 215" />
      </circle>
      <circle r="2" fill="#e3a615" opacity="0.5">
        <animateMotion dur="5s" repeatCount="indefinite" begin="1.5s" path="M50 220 Q130 200 200 210 Q280 220 370 215" />
      </circle>

      {/* ── 港口起重机（右侧/远景） ── */}
      <g transform="translate(340, 110)" opacity="0.4">
        <rect x="5" y="15" width="3" height="45" fill="#3a5068" />
        <rect x="15" y="15" width="3" height="45" fill="#3a5068" />
        <rect x="0" y="12" width="35" height="3" rx="1" fill="#4a6078" />
        <rect x="2" y="60" width="20" height="3" rx="1" fill="#2a3a50" />
      </g>

      {/* ── 右下角：小飞机（空运暗示） ── */}
      <g opacity="0.12">
        <path d="M320 25 L330 22 L340 25 L335 26 L340 30 L333 27 L330 30 L331 26 L325 28 Z" fill="white">
          <animateTransform attributeName="transform" type="translate" values="0,0;50,-15;0,0" dur="12s" repeatCount="indefinite" />
        </path>
      </g>
    </svg>
  );
}
