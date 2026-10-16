"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Anchor,
  ArrowLeft,
  CheckCircle2,
  Container,
  FileCheck,
  Package,
  Ship,
  Warehouse,
  Waypoints,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  BFF_ORDERS_SOURCE,
  formatDecimalString,
  type BindingState,
  type OrdersSource,
  type PortalOrderDetail,
  type PortalOrderLine,
  type PortalShipment,
} from "@/lib/api/buyerOrders";
import {
  CustomsPill,
  KeyDateLine,
  LoadingSkeleton,
  Money,
  StagePill,
  StatePanel,
  ValueSegmentBar,
  useDay,
  useDayTime,
} from "./buyerOrdersShared";
import { FULFILLMENT_NODES, countReceivedLines, lineInWarehouse, litNodes, pendingLines, type NodeKey } from "./orderProgress";

type DetailState =
  | { kind: "loading" }
  | { kind: "binding"; binding: BindingState }
  | { kind: "unavailable" }
  | { kind: "not_found" }
  | { kind: "data"; order: PortalOrderDetail };

export function BuyerOrderDetail({
  no,
  onBack,
  source = BFF_ORDERS_SOURCE,
}: {
  no: string;
  onBack: () => void;
  source?: OrdersSource;
}) {
  const t = useTranslations("orderTracking");
  const [state, setState] = useState<DetailState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const res = await source.detail(no);
      if (res.kind === "binding") setState({ kind: "binding", binding: res.binding });
      else setState({ kind: "data", order: res.order });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setState({ kind: "not_found" });
      else setState({ kind: "unavailable" }); // 含刷新后仍 401:不停在骨架屏
    }
  }, [no, source]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-muted hover:text-teal-700 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("backToList")}
      </button>

      {state.kind === "loading" && <LoadingSkeleton rows={2} />}
      {state.kind === "binding" && <StatePanel kind={state.binding} />}
      {state.kind === "unavailable" && <StatePanel kind="UNAVAILABLE" onRetry={load} />}
      {state.kind === "not_found" && (
        <div className="rounded-xl border border-line bg-white p-16 text-center">
          <Package className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-navy">{t("orderNotFound")}</h3>
        </div>
      )}
      {state.kind === "data" && <DetailBody order={state.order} />}
    </div>
  );
}

/** tab 身份:柜按下标,「待装柜」固定一个。 */
type Tab = { kind: "shipment"; index: number } | { kind: "pending" };

function DetailBody({ order }: { order: PortalOrderDetail }) {
  const t = useTranslations("orderTracking");
  const day = useDay();
  const shipments = order.shipments;
  const lines = [...order.lines].sort((a, b) => a.sort_order - b.sort_order);
  const pending = pendingLines(order.lines);
  const cancelled = order.stage === "CANCELLED";
  // 柜 tab 在前,「待装柜」并列在后(仅当还有未装柜的货);默认停在第一个 tab
  const [tab, setTab] = useState<Tab>(shipments.length > 0 ? { kind: "shipment", index: 0 } : { kind: "pending" });
  const activeShipment =
    tab.kind === "shipment" ? shipments[Math.min(tab.index, Math.max(0, shipments.length - 1))] ?? null : null;
  const showTabs = shipments.length + (pending.length > 0 ? 1 : 0) > 1;

  return (
    <>
      {/* 概览:徽标 + 关键日期行 + 按货值分段条(契约 §5.3 v5) */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div
          className="px-6 py-5"
          style={{ background: "linear-gradient(135deg, #e2edcd 0%, #eef4e6 55%, #eef7dc 100%)" }}
        >
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-xl font-bold text-navy font-mono">{order.no}</h2>
                <StagePill stage={order.stage} size="md" />
              </div>
              <div className="mt-2 flex items-center gap-x-4 gap-y-1 text-sm text-muted flex-wrap">
                <span>
                  {t("orderDate")}: {day(order.created_at)}
                </span>
                <span>{t("lineCount", { count: order.line_count })}</span>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted">{t("totalAmount")}</p>
              <Money amount={order.total_amount} currency={order.currency} className="text-xl font-bold text-navy" />
            </div>
          </div>
          {cancelled ? (
            <p className="mt-3 text-sm text-muted">{t("cancelledNote")}</p>
          ) : (
            <div className="mt-4 space-y-2">
              <KeyDateLine shipmentCount={order.shipment_count} nextEta={order.next_eta} stage={order.stage} />
              <p className="text-xs text-muted">{t("valueProgress")}</p>
              <ValueSegmentBar segments={order.value_segments} legend />
            </div>
          )}
        </div>
      </div>

      {/* 物流:柜 tab(柜头 + 六节点时间线 + 本柜货物)/「待装柜」tab(时间线 + 待装行) */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <Ship className="h-5 w-5 text-teal-700" />
            {t("shipmentTracking")}
          </h3>
        </div>

        {cancelled ? (
          // 取消单不画进度
          <p className="px-6 py-8 text-sm text-muted text-center">{t("cancelledNote")}</p>
        ) : (
          <>
            {showTabs && (
              <div className="px-6 pt-3 flex gap-2 border-b border-line overflow-x-auto">
                {shipments.map((s, i) => (
                  <TabButton
                    key={`${s.container_no}-${i}`}
                    active={tab.kind === "shipment" && tab.index === i}
                    onClick={() => setTab({ kind: "shipment", index: i })}
                  >
                    <span className="font-mono">{s.container_no ?? t("containerPending")}</span>
                    {s.container_type && <span className="ml-2 text-xs text-muted">({s.container_type})</span>}
                  </TabButton>
                ))}
                {pending.length > 0 && (
                  <TabButton active={tab.kind === "pending"} onClick={() => setTab({ kind: "pending" })}>
                    <Warehouse className="inline h-4 w-4 mr-1.5 -mt-0.5" />
                    {t("pendingTab")}
                    <span className="ml-1.5 text-xs text-muted">({pending.length})</span>
                  </TabButton>
                )}
              </div>
            )}
            {activeShipment ? (
              <>
                <ShipmentHeader shipment={activeShipment} />
                <NodeTimeline order={order} shipment={activeShipment} />
                <ShipmentLinesTable shipment={activeShipment} />
              </>
            ) : (
              <>
                <NodeTimeline order={order} shipment={null} />
                <PendingLinesTable lines={pending} />
              </>
            )}
          </>
        )}
      </div>

      {/* 行明细 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <Package className="h-5 w-5 text-teal-700" />
            {t("orderItems")}
            <span className="text-sm font-normal text-muted">({t("lineCount", { count: lines.length })})</span>
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                <th className="px-6 py-3 font-medium text-muted">{t("colProduct")}</th>
                <th className="px-4 py-3 font-medium text-muted text-right whitespace-nowrap">{t("colQtyProgress")}</th>
                <th className="px-4 py-3 font-medium text-muted text-right whitespace-nowrap">{t("colUnitPrice")}</th>
                <th className="px-6 py-3 font-medium text-muted text-right whitespace-nowrap">{t("colSubtotal")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lines.map((line, i) => (
                <tr key={`${line.sort_order}-${i}`} className="hover:bg-slate-50/50">
                  <td className="px-6 py-3">
                    <p className="font-medium text-navy">{line.name_snapshot}</p>
                    {line.spec_text_snapshot && (
                      <p className="text-xs text-muted">{line.spec_text_snapshot}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-navy whitespace-nowrap">
                    {t("qtyProgress", {
                      received: formatDecimalString(line.received_qty),
                      shipped: formatDecimalString(line.shipped_qty),
                      qty: formatDecimalString(line.qty),
                    })}{" "}
                    <span className="text-xs text-muted">{line.unit_label}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-navy whitespace-nowrap">
                    <Money amount={line.unit_price} currency={order.currency} />
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-navy whitespace-nowrap">
                    <Money amount={line.line_total} currency={order.currency} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`whitespace-nowrap px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
        active ? "border-teal-700 text-teal-700 bg-teal-50" : "border-transparent text-muted hover:text-navy"
      }`}
    >
      {children}
    </button>
  );
}

/* ── 柜头:柜号 / 航线 / 船名航次 / 报关状态 ── */

function ShipmentHeader({ shipment }: { shipment: PortalShipment }) {
  const t = useTranslations("orderTracking");
  const day = useDay();
  return (
    <div className="px-6 pt-6 flex items-center gap-x-6 gap-y-2 text-sm flex-wrap">
      <div className="flex items-center gap-2">
        <Container className="h-4 w-4 text-teal-700" />
        <span className="text-muted">{t("containerNo")}:</span>
        <span className="font-mono font-medium text-navy">{shipment.container_no ?? t("containerPending")}</span>
        {shipment.container_type && <span className="text-xs text-muted">({shipment.container_type})</span>}
      </div>
      <div className="flex items-center gap-2">
        <Anchor className="h-4 w-4 text-teal-700" />
        <span className="text-muted">{t("route")}:</span>
        <span className="font-medium text-navy">
          {shipment.port_of_loading ?? "—"} → {shipment.port_of_discharge ?? "—"}
        </span>
      </div>
      {shipment.vessel_name && (
        <div className="flex items-center gap-2">
          <Ship className="h-4 w-4 text-teal-700" />
          <span className="text-muted">{t("vesselName")}:</span>
          <span className="font-medium text-navy">{shipment.vessel_name}</span>
        </div>
      )}
      {shipment.voyage_no && (
        <div className="flex items-center gap-2">
          <span className="text-muted">{t("voyageNo")}:</span>
          <span className="font-mono font-medium text-navy">{shipment.voyage_no}</span>
        </div>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <FileCheck className="h-4 w-4 text-teal-700" />
        <span className="text-muted">{t("customsStatus")}:</span>
        <CustomsPill status={shipment.customs_status} />
        {shipment.declared_at && (
          <span className="text-xs text-muted">{t("declaredOn", { date: day(shipment.declared_at) })}</span>
        )}
        {shipment.released_at && (
          <span className="text-xs text-muted">{t("releasedOn", { date: day(shipment.released_at) })}</span>
        )}
      </div>
      <StagePill stage={shipment.stage} />
    </div>
  );
}

/* ── 本柜货物:品名 / 规格 / 数量 单位(无价,契约 §4.2 v5) ── */

function ShipmentLinesTable({ shipment }: { shipment: PortalShipment }) {
  const t = useTranslations("orderTracking");
  const rows = [...shipment.lines].sort((a, b) => a.sort_order - b.sort_order);
  return (
    <div className="border-t border-line">
      <h4 className="px-6 pt-4 pb-2 text-sm font-semibold text-navy flex items-center gap-2">
        <Package className="h-4 w-4 text-teal-700" />
        {t("containerGoods")}
        <span className="font-normal text-muted">({t("lineCount", { count: rows.length })})</span>
      </h4>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-left">
            <th className="px-6 py-2 font-medium text-muted">{t("colProduct")}</th>
            <th className="px-6 py-2 font-medium text-muted text-right whitespace-nowrap">{t("colQty")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((line, i) => (
            <tr key={`${line.sort_order}-${i}`}>
              <td className="px-6 py-2.5">
                <p className="font-medium text-navy">{line.name_snapshot}</p>
                {line.spec_text_snapshot && <p className="text-xs text-muted">{line.spec_text_snapshot}</p>}
              </td>
              <td className="px-6 py-2.5 text-right text-navy whitespace-nowrap">
                {formatDecimalString(line.qty)} <span className="text-xs text-muted">{line.unit_label}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── 待装柜:品名 / 待装数量 / 入仓情况(已入仓 / 未到齐 · 在仓 a) ── */

function PendingLinesTable({ lines }: { lines: PortalOrderLine[] }) {
  const t = useTranslations("orderTracking");
  if (lines.length === 0) return null;
  return (
    <div className="border-t border-line">
      <p className="px-6 pt-4 pb-2 text-sm text-muted">{t("pendingNote")}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-left">
            <th className="px-6 py-2 font-medium text-muted">{t("colProduct")}</th>
            <th className="px-4 py-2 font-medium text-muted text-right whitespace-nowrap">{t("colPendingQty")}</th>
            <th className="px-6 py-2 font-medium text-muted text-right whitespace-nowrap">{t("colWarehouseStatus")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {lines.map((line, i) => {
            const ready = lineInWarehouse(line);
            return (
              <tr key={`${line.sort_order}-${i}`}>
                <td className="px-6 py-2.5">
                  <p className="font-medium text-navy">{line.name_snapshot}</p>
                  {line.spec_text_snapshot && <p className="text-xs text-muted">{line.spec_text_snapshot}</p>}
                </td>
                <td className="px-4 py-2.5 text-right text-navy whitespace-nowrap">
                  {formatDecimalString(line.pending_qty)} <span className="text-xs text-muted">{line.unit_label}</span>
                </td>
                <td className="px-6 py-2.5 text-right whitespace-nowrap">
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      ready ? "bg-green-50 text-green-700 border-green-200" : "bg-amber-50 text-amber-700 border-amber-200"
                    }`}
                  >
                    {ready ? t("inWarehouse") : t("notFullyReceived", { qty: formatDecimalString(line.in_warehouse_qty) })}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── 六节点时间线:逐节点按事实点亮(orderProgress.litNodes),不按序号补亮 ── */

const NODE_ICONS: Record<NodeKey, React.ElementType> = {
  msOrderConfirmed: CheckCircle2,
  msWarehouseReceipt: Warehouse,
  msConsolidation: Container,
  msCustomsExport: FileCheck,
  msSeaFreight: Ship,
  msPortArrival: Anchor,
};

type Row = {
  key: string;
  labelKey: string;
  icon: React.ElementType;
  lit: boolean;
  detail: string | null;
};

function NodeTimeline({ order, shipment }: { order: PortalOrderDetail; shipment: PortalShipment | null }) {
  const t = useTranslations("orderTracking");
  const day = useDay();
  const dayTime = useDayTime();
  const lit = litNodes(order, shipment);
  const at = (date: string | null | undefined, location?: string | null) =>
    date ? `${dayTime(date)}${location ? ` · ${location}` : ""}` : null;
  // 未发生节点的计划行:无计划日期就不显示(裸港口名会被误读成已发生事件)
  const plan = (key: "etdOn" | "etaOn", date: string | null, location: string | null) =>
    date ? `${t(key, { date: day(date) })}${location ? ` · ${location}` : ""}` : null;

  const detailOf = (key: NodeKey, isLit: boolean): string | null => {
    switch (key) {
      case "msOrderConfirmed":
        return null;
      case "msWarehouseReceipt":
        // 订单级副文案:柜视图里节点按本柜点亮,这行说明整单还备齐了几行
        return t("receivedLines", { done: countReceivedLines(order.lines), total: order.lines.length });
      case "msConsolidation":
        return isLit && shipment ? at(shipment.loaded_at) : null;
      case "msCustomsExport":
        if (!shipment) return null;
        if (shipment.released_at) return t("releasedOn", { date: day(shipment.released_at) });
        if (shipment.declared_at) return t("declaredOn", { date: day(shipment.declared_at) });
        return null;
      case "msSeaFreight":
        // 离港以 atd 为准(契约:DEPARTED 取自 atd);未离港显示 ETD 计划
        if (!shipment) return null;
        return isLit ? at(shipment.atd, shipment.port_of_loading) : plan("etdOn", shipment.etd, shipment.port_of_loading);
      case "msPortArrival": {
        if (!shipment) return null;
        const arrived = shipment.milestones.find((m) => m.type === "ARRIVED");
        return arrived
          ? at(arrived.event_at, arrived.location ?? shipment.port_of_discharge)
          : plan("etaOn", shipment.eta, shipment.port_of_discharge);
      }
    }
  };

  const rows: Row[] = FULFILLMENT_NODES.map((key, i) => ({
    key,
    labelKey: key,
    icon: NODE_ICONS[key],
    lit: lit[i],
    detail: detailOf(key, lit[i]),
  }));
  // 中转是海运途中的已发生事件,挂在"海运在途"之后,不计入六节点
  if (shipment) {
    const transshipments = shipment.milestones.filter((m) => m.type === "TRANSSHIPMENT");
    const seaIdx = rows.findIndex((r) => r.key === "msSeaFreight");
    rows.splice(
      seaIdx + 1,
      0,
      ...transshipments.map((m, i) => ({
        key: `trans-${i}`,
        labelKey: "msTransshipment",
        icon: Waypoints,
        lit: true,
        detail: at(m.event_at, m.location),
      })),
    );
  }

  return (
    <div className="p-6">
      <div className="relative">
        {rows.map((row, i) => {
          const Icon = row.icon;
          const isLast = i === rows.length - 1;
          return (
            <div key={row.key} className="relative flex gap-4 pb-6">
              <div className="relative flex flex-col items-center">
                <div
                  className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 ${
                    row.lit ? "border-teal-500 bg-teal-500 text-white" : "border-slate-200 bg-white text-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                {!isLast && (
                  <div
                    // 连线只在两端都已点亮时着色,不暗示"灭节点已走过"
                    className={`absolute top-9 w-0.5 ${row.lit && rows[i + 1].lit ? "bg-teal-400" : "bg-slate-200"}`}
                    style={{ height: "calc(100% - 12px)" }}
                  />
                )}
              </div>
              <div className="flex-1 pt-1.5 min-w-0">
                <span className={`text-sm font-semibold ${row.lit ? "text-navy" : "text-muted"}`}>
                  {t(row.labelKey)}
                </span>
                {row.detail && <p className="mt-0.5 text-xs text-muted">{row.detail}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
