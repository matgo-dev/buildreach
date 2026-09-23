"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Anchor, Ban, CheckCircle2, ChevronRight, Package, Ship, Warehouse } from "lucide-react";
import {
  BFF_ORDERS_SOURCE,
  type BindingState,
  type OrderPage,
  type OrderStage,
  type OrdersSource,
  type PortalOrderListItem,
} from "@/lib/api/buyerOrders";
import Pagination from "@/components/ui/Pagination";
import { BuyerOrderDetail } from "./BuyerOrderDetail";
import { EmptyOrdersState, LoadingSkeleton, Money, StagePill, StatePanel, stageLabelKey, useDay } from "./buyerOrdersShared";
import { FulfillmentHeroBanner, StatCard } from "./orderTrackingVisuals";
import { stageProgress } from "./orderProgress";

// 一页拉满契约上限:客户一年几单,多年也在一页内,统计卡计数与下钻因此就是全量;超 100 单才翻页。
// 超 100 单后统计卡与下钻只覆盖当前页,那是把筛选与计数移到履约服务端的触发信号,不是在前端加第二页统计。
const PAGE_SIZE = 100;

/** 统计卡四桶(契约 §5.3,单一源头):卡片计数与点击下钻都只从这里取阶段集合。
 *  每个 OrderStage 恰属一个桶,四桶之和 = "全部"(履约回的 total)。 */
const STAGE_FILTERS = {
  PREPARING: ["CONFIRMED", "RECEIVED"],
  SHIPPING: ["LOADED", "CLEARED", "IN_TRANSIT"],
  ARRIVED: ["ARRIVED"],
  CANCELLED: ["CANCELLED"],
} as const satisfies Record<string, readonly OrderStage[]>;

type Bucket = keyof typeof STAGE_FILTERS;
type StageFilter = "ALL" | Bucket;

// 编译期守:OrderStage 新增值而未归桶时,下一行类型报错
type BucketedStage = (typeof STAGE_FILTERS)[Bucket][number];
const _EVERY_STAGE_BUCKETED: [OrderStage] extends [BucketedStage] ? true : never = true;
void _EVERY_STAGE_BUCKETED;

function inBucket(bucket: Bucket, stage: string): boolean {
  return (STAGE_FILTERS[bucket] as readonly string[]).includes(stage);
}

type ListState =
  | { kind: "loading" }
  | { kind: "binding"; binding: BindingState }
  | { kind: "unavailable" }
  | { kind: "data"; page: OrderPage };

/** 「我的订单」:列表 ⇄ 详情。真实用户数据实时来自履约后台(经 BFF);demo 账号注入 mock 数据源。 */
export function BuyerOrders({ source = BFF_ORDERS_SOURCE }: { source?: OrdersSource }) {
  const [page, setPage] = useState(1);
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [selectedNo, setSelectedNo] = useState<string | null>(null);
  // 请求序号:快速翻页时晚到的旧响应不得覆盖新页
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ kind: "loading" });
    try {
      const res = await source.list(page, PAGE_SIZE);
      if (mine !== seq.current) return;
      if (res.kind === "binding") setState({ kind: "binding", binding: res.binding });
      else setState({ kind: "data", page: res.page });
    } catch {
      if (mine !== seq.current) return;
      // 503 / 形状不对 / 刷新后仍 401 一律落到"不可用 + 重试"面板,不停在骨架屏;
      // 会话真失效时 api 层已清 store,RouteGuard 会卸载本页
      setState({ kind: "unavailable" });
    }
  }, [page, source]);

  useEffect(() => {
    void load();
  }, [load]);

  if (selectedNo) {
    return <BuyerOrderDetail no={selectedNo} source={source} onBack={() => setSelectedNo(null)} />;
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
  // 统计卡点击下钻:在已加载的一页内筛;PAGE_SIZE=100 覆盖任何现实客户的全部订单(契约 §9 登记超限再做服务端)
  const [filter, setFilter] = useState<StageFilter>("ALL");
  const count = (bucket: Bucket) => items.filter((o) => inBucket(bucket, o.stage)).length;
  const visible = filter === "ALL" ? items : items.filter((o) => inBucket(filter, o.stage));
  const toggle = (f: StageFilter) => setFilter((cur) => (cur === f ? "ALL" : f));

  if (total === 0) return <EmptyOrdersState />;

  return (
    <>
      {/* 五张卡:手机两列(末张独占一格),平板三列,桌面一行五张 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard icon={Package} label={t("statTotal")} value={String(total)} color="text-teal-700 bg-teal-50" onClick={() => setFilter("ALL")} active={filter === "ALL"} />
        <StatCard icon={Warehouse} label={t("statPreparing")} value={String(count("PREPARING"))} color="text-amber-700 bg-amber-50" onClick={() => toggle("PREPARING")} active={filter === "PREPARING"} />
        <StatCard icon={Ship} label={t("statShipping")} value={String(count("SHIPPING"))} color="text-blue-700 bg-blue-50" onClick={() => toggle("SHIPPING")} active={filter === "SHIPPING"} />
        <StatCard icon={CheckCircle2} label={t("statArrived")} value={String(count("ARRIVED"))} color="text-green-700 bg-green-50" onClick={() => toggle("ARRIVED")} active={filter === "ARRIVED"} />
        <StatCard icon={Ban} label={t("statCancelled")} value={String(count("CANCELLED"))} color="text-slate-500 bg-slate-100" onClick={() => toggle("CANCELLED")} active={filter === "CANCELLED"} />
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
  const progress = stageProgress(order.stage);
  const labelKey = stageLabelKey(order.stage);

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

          {/* 阶段进度条:订单 stage 驱动的展示百分比;CANCELLED 与不认识的 stage 不画 */}
          {progress !== null && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-muted mb-1.5">
                <span className="flex items-center gap-1">
                  <Anchor className="h-3 w-3" />
                  {labelKey ? t(labelKey) : order.stage}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </div>
        <ChevronRight className="h-5 w-5 text-muted group-hover:text-teal-700 shrink-0 mt-2 transition-colors" />
      </div>
    </button>
  );
}
