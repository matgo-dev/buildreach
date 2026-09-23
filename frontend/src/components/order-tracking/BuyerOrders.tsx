"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Anchor, CheckCircle2, ChevronRight, Package, Ship, Warehouse } from "lucide-react";
import {
  getBuyerOrders,
  type BindingState,
  type OrderPage,
  type PortalOrderListItem,
} from "@/lib/api/buyerOrders";
import Pagination from "@/components/ui/Pagination";
import { BuyerOrderDetail } from "./BuyerOrderDetail";
import { EmptyOrdersState, LoadingSkeleton, Money, StagePill, StatePanel, useDay } from "./buyerOrdersShared";
import { FulfillmentHeroBanner, STAGE_PROGRESS, StatCard } from "./orderTrackingVisuals";

const PAGE_SIZE = 20;

type StageFilter = "ALL" | "PREPARING" | "TRANSIT" | "ARRIVED";
const STAGE_FILTERS: Record<Exclude<StageFilter, "ALL">, PortalOrderListItem["stage"][]> = {
  PREPARING: ["CONFIRMED"],
  TRANSIT: ["LOADED", "IN_TRANSIT"],
  ARRIVED: ["ARRIVED"],
};

const STAGE_KEY: Record<string, string> = {
  CONFIRMED: "Confirmed", LOADED: "Loaded", IN_TRANSIT: "InTransit", ARRIVED: "Arrived", CANCELLED: "Cancelled",
};

type ListState =
  | { kind: "loading" }
  | { kind: "binding"; binding: BindingState }
  | { kind: "unavailable" }
  | { kind: "data"; page: OrderPage };

/** 真实用户的「我的订单」:列表 ⇄ 详情,数据实时来自履约后台(经 BFF)。 */
export function BuyerOrders() {
  const [page, setPage] = useState(1);
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [selectedNo, setSelectedNo] = useState<string | null>(null);
  // 请求序号:快速翻页时晚到的旧响应不得覆盖新页
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ kind: "loading" });
    try {
      const res = await getBuyerOrders(page, PAGE_SIZE);
      if (mine !== seq.current) return;
      if (res.kind === "binding") setState({ kind: "binding", binding: res.binding });
      else setState({ kind: "data", page: res.page });
    } catch {
      if (mine !== seq.current) return;
      // 503 / 形状不对 / 刷新后仍 401 一律落到"不可用 + 重试"面板,不停在骨架屏;
      // 会话真失效时 api 层已清 store,RouteGuard 会卸载本页
      setState({ kind: "unavailable" });
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  if (selectedNo) {
    return <BuyerOrderDetail no={selectedNo} onBack={() => setSelectedNo(null)} />;
  }

  return (
    <div className="space-y-6">
      <FulfillmentHeroBanner />
      {state.kind === "loading" && <LoadingSkeleton />}
      {state.kind === "binding" && <StatePanel kind={state.binding} />}
      {state.kind === "unavailable" && <StatePanel kind="UNAVAILABLE" onRetry={load} />}
      {state.kind === "data" && (
        <OrderList page={state.page} onSelect={setSelectedNo} onPageChange={setPage} />
      )}
    </div>
  );
}

function OrderList({
  page,
  onSelect,
  onPageChange,
}: {
  page: OrderPage;
  onSelect: (no: string) => void;
  onPageChange: (p: number) => void;
}) {
  const t = useTranslations("orderTracking");
  const { items, total, size } = page;
  const totalPages = Math.max(1, Math.ceil(total / size));
  // 统计卡点击下钻:当前只在已加载的这一页内筛(履约接口暂无 stage 过滤,契约 v4 登记服务端筛选与全量计数)
  const [filter, setFilter] = useState<StageFilter>("ALL");
  const count = (...stages: PortalOrderListItem["stage"][]) => items.filter((o) => stages.includes(o.stage)).length;
  const visible = filter === "ALL" ? items : items.filter((o) => STAGE_FILTERS[filter].includes(o.stage));
  const toggle = (f: StageFilter) => setFilter((cur) => (cur === f ? "ALL" : f));

  if (total === 0) return <EmptyOrdersState />;

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Package} label={t("statTotal")} value={String(total)} color="text-teal-700 bg-teal-50" onClick={() => setFilter("ALL")} active={filter === "ALL"} />
        <StatCard icon={Warehouse} label={t("statPreparing")} value={String(count("CONFIRMED"))} color="text-amber-700 bg-amber-50" onClick={() => toggle("PREPARING")} active={filter === "PREPARING"} />
        <StatCard icon={Ship} label={t("statInTransit")} value={String(count("LOADED", "IN_TRANSIT"))} color="text-blue-700 bg-blue-50" onClick={() => toggle("TRANSIT")} active={filter === "TRANSIT"} />
        <StatCard icon={CheckCircle2} label={t("statArrived")} value={String(count("ARRIVED"))} color="text-green-700 bg-green-50" onClick={() => toggle("ARRIVED")} active={filter === "ARRIVED"} />
      </div>

      {visible.length === 0 && (
        <p className="rounded-xl border border-dashed border-line bg-white px-6 py-8 text-center text-sm text-muted">{t("filterEmpty")}</p>
      )}
      <div className="space-y-4">
        {visible.map((order) => (
          <OrderCard key={order.no} order={order} onClick={() => onSelect(order.no)} />
        ))}
      </div>

      {totalPages > 1 && (
        <Pagination current={page.page} total={totalPages} totalItems={total} onChange={onPageChange} />
      )}
    </>
  );
}

function OrderCard({ order, onClick }: { order: PortalOrderListItem; onClick: () => void }) {
  const t = useTranslations("orderTracking");
  const day = useDay();

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left rounded-xl border border-line bg-white p-5 hover:shadow-md hover:border-teal-200 transition-all group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-sm font-semibold text-navy">{order.no}</span>
            <StagePill stage={order.stage} />
          </div>
          <div className="mt-2.5 flex items-center gap-x-4 gap-y-1 text-sm text-muted flex-wrap">
            <span>
              {t("orderDate")}: {day(order.created_at)}
            </span>
            <span>{t("lineCount", { count: order.line_count })}</span>
          </div>
          <div className="mt-2 text-base font-semibold text-navy">
            <Money amount={order.total_amount} currency={order.currency} />
          </div>

          {/* 阶段进度条:按阶段映射的展示百分比 */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-muted mb-1.5">
              <span className="flex items-center gap-1">
                <Anchor className="h-3 w-3" />
                {t(`stage${STAGE_KEY[order.stage] ?? "Confirmed"}`)}
              </span>
              <span>{STAGE_PROGRESS[order.stage] ?? 0}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400 transition-all"
                style={{ width: `${STAGE_PROGRESS[order.stage] ?? 0}%` }}
              />
            </div>
          </div>
        </div>
        <ChevronRight className="h-5 w-5 text-muted group-hover:text-teal-700 shrink-0 mt-2 transition-colors" />
      </div>
    </button>
  );
}
