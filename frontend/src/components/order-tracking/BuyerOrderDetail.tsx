"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Anchor, ArrowLeft, Circle, Container, Package, Ship, Waypoints } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  formatDecimalString,
  getBuyerOrder,
  type BindingState,
  type PortalOrderDetail,
  type PortalShipment,
} from "@/lib/api/buyerOrders";
import { LoadingSkeleton, Money, StagePill, StatePanel, useDay, useDayTime } from "./buyerOrdersShared";

type DetailState =
  | { kind: "loading" }
  | { kind: "binding"; binding: BindingState }
  | { kind: "unavailable" }
  | { kind: "not_found" }
  | { kind: "data"; order: PortalOrderDetail };

export function BuyerOrderDetail({ no, onBack }: { no: string; onBack: () => void }) {
  const t = useTranslations("orderTracking");
  const [state, setState] = useState<DetailState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const res = await getBuyerOrder(no);
      if (res.kind === "binding") setState({ kind: "binding", binding: res.binding });
      else setState({ kind: "data", order: res.order });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setState({ kind: "not_found" });
      else setState({ kind: "unavailable" }); // 含刷新后仍 401:不停在骨架屏
    }
  }, [no]);

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

function DetailBody({ order }: { order: PortalOrderDetail }) {
  const t = useTranslations("orderTracking");
  const day = useDay();
  const [active, setActive] = useState(0);
  const shipments = order.shipments;
  const lines = [...order.lines].sort((a, b) => a.sort_order - b.sort_order);
  const activeShipment = shipments[Math.min(active, Math.max(0, shipments.length - 1))];

  return (
    <>
      {/* 概览 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div
          className="px-6 py-5"
          style={{ background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 50%, #f0f9ff 100%)" }}
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
          {order.stage === "CANCELLED" && (
            <p className="mt-3 text-sm text-slate-500">{t("cancelledNote")}</p>
          )}
        </div>
      </div>

      {/* 物流:按柜各自时间线 */}
      <div className="rounded-xl border border-line bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="text-lg font-semibold text-navy flex items-center gap-2">
            <Ship className="h-5 w-5 text-teal-700" />
            {t("shipmentTracking")}
          </h3>
        </div>

        {shipments.length === 0 ? (
          <p className="px-6 py-8 text-sm text-muted text-center">
            {order.stage === "CANCELLED" ? t("cancelledNote") : t("noShipmentYet")}
          </p>
        ) : (
          <>
            {shipments.length > 1 && (
              <div className="px-6 pt-3 flex gap-2 border-b border-line overflow-x-auto">
                {shipments.map((s, i) => (
                  <button
                    key={`${s.container_no}-${i}`}
                    type="button"
                    onClick={() => setActive(i)}
                    className={`whitespace-nowrap px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
                      i === active
                        ? "border-teal-700 text-teal-700 bg-teal-50"
                        : "border-transparent text-muted hover:text-navy"
                    }`}
                  >
                    <span className="font-mono">{s.container_no ?? t("containerPending")}</span>
                    {s.container_type && <span className="ml-2 text-xs text-muted">({s.container_type})</span>}
                  </button>
                ))}
              </div>
            )}
            {activeShipment && <ShipmentTimeline shipment={activeShipment} muted={order.stage === "CANCELLED"} />}
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
                <th className="px-4 py-3 font-medium text-muted text-right whitespace-nowrap">{t("colShippedQty")}</th>
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
                    {t("shippedOfTotal", {
                      shipped: formatDecimalString(line.shipped_qty),
                      qty: formatDecimalString(line.qty),
                    })}{" "}
                    <span className="text-xs text-muted">{line.unit_label}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-navy whitespace-nowrap">
                    {formatDecimalString(line.unit_price)}
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-navy whitespace-nowrap">
                    {formatDecimalString(line.line_total)}
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

/* ── 柜级时间线:装柜 → 离港 → (中转…) → 到港 ── */

type Step = {
  key: string;
  labelKey: string;
  icon: React.ElementType;
  status: "done" | "current" | "upcoming";
  when: string | null;
  whenPrefix?: "ETD" | "ETA";
  location?: string | null;
};

function buildSteps(s: PortalShipment): Step[] {
  const departed = s.milestones.find((m) => m.type === "DEPARTED");
  const arrived = s.milestones.find((m) => m.type === "ARRIVED");
  const transshipments = s.milestones.filter((m) => m.type === "TRANSSHIPMENT");

  const loadedStatus = "done" as const;
  const departedStatus = s.stage === "LOADED" ? "current" : "done";
  const arrivedStatus = s.stage === "ARRIVED" ? "done" : s.stage === "IN_TRANSIT" ? "current" : "upcoming";

  const steps: Step[] = [
    { key: "loaded", labelKey: "msLoaded", icon: Container, status: loadedStatus, when: s.loaded_at },
    {
      key: "departed",
      labelKey: "msDeparted",
      icon: Ship,
      status: departedStatus,
      // 离港以 atd 为准(契约:DEPARTED 取自 atd);未离港显示 ETD 计划
      when: s.atd ?? departed?.event_at ?? s.etd,
      whenPrefix: s.atd || departed ? undefined : "ETD",
      location: s.port_of_loading,
    },
    ...transshipments.map((m, i) => ({
      key: `trans-${i}`,
      labelKey: "msTransshipment",
      icon: Waypoints,
      status: "done" as const, // 有中转事件即已发生
      when: m.event_at,
      location: m.location,
    })),
    {
      key: "arrived",
      labelKey: "msArrived",
      icon: Anchor,
      status: arrivedStatus,
      when: arrived?.event_at ?? s.eta,
      whenPrefix: arrived ? undefined : "ETA",
      location: arrived?.location ?? s.port_of_discharge,
    },
  ];
  return steps;
}

function ShipmentTimeline({ shipment, muted }: { shipment: PortalShipment; muted: boolean }) {
  const t = useTranslations("orderTracking");
  const dayTime = useDayTime();
  const steps = buildSteps(shipment);

  return (
    <div className="p-6">
      <div className="flex items-center gap-x-6 gap-y-2 mb-6 text-sm flex-wrap">
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
        <StagePill stage={shipment.stage} />
      </div>

      <div className="relative">
        {steps.map((step, i) => {
          const Icon = step.icon ?? Circle;
          const isLast = i === steps.length - 1;
          const status = muted ? "upcoming" : step.status;
          return (
            <div key={step.key} className="relative flex gap-4 pb-6">
              <div className="relative flex flex-col items-center">
                <div
                  className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 ${
                    status === "done"
                      ? "border-teal-500 bg-teal-500 text-white"
                      : status === "current"
                      ? "border-teal-500 bg-white text-teal-700 ring-4 ring-teal-100"
                      : "border-slate-200 bg-white text-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                {!isLast && (
                  <div
                    className={`absolute top-9 w-0.5 ${status === "done" ? "bg-teal-400" : "bg-slate-200"}`}
                    style={{ height: "calc(100% - 12px)" }}
                  />
                )}
              </div>
              <div className="flex-1 pt-1.5 min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span
                    className={`text-sm font-semibold ${
                      status === "done" ? "text-navy" : status === "current" ? "text-teal-700" : "text-slate-400"
                    }`}
                  >
                    {t(step.labelKey)}
                  </span>
                  {status === "current" && (
                    <span className="inline-flex items-center rounded-full bg-teal-100 border border-teal-200 px-2 py-0.5 text-[11px] font-medium text-teal-700">
                      {t("currentStep")}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {step.whenPrefix && step.when ? `${step.whenPrefix} ` : ""}
                  {dayTime(step.when)}
                  {step.location ? ` · ${step.location}` : ""}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
