"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  getBuyerOrders,
  type BindingState,
  type OrderPage,
  type PortalOrderListItem,
} from "@/lib/api/buyerOrders";
import Pagination from "@/components/ui/Pagination";
import { BuyerOrderDetail } from "./BuyerOrderDetail";
import { EmptyOrdersState, LoadingSkeleton, Money, PageHeader, StagePill, StatePanel, useDay } from "./buyerOrdersShared";

const PAGE_SIZE = 20;

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
    } catch (err) {
      if (mine !== seq.current) return;
      // 503(履约不可达)与其它异常同一处理:提示稍后重试;401 已由 api 层刷新/清会话
      if (err instanceof ApiError && err.status === 401) return;
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
      <PageHeader />
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

  if (total === 0) return <EmptyOrdersState />;

  return (
    <>
      <div className="space-y-4">
        {items.map((order) => (
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
        </div>
        <ChevronRight className="h-5 w-5 text-muted group-hover:text-teal-700 shrink-0 mt-2 transition-colors" />
      </div>
    </button>
  );
}
