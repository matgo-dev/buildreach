// 六节点点亮与按货值分段的纯派生(契约 docs/specs/2026-09-21-0214 §5.3 v5)。
// 只测纯 ts:上一次 litNodes 节点 2 的口径 bug 正是藏在这里,tsc 挡不住。
import { describe, expect, it } from "vitest";
import type { PortalOrderLine, PortalShipment, PortalValueSegments } from "@/lib/api/buyerOrders";
import {
  FULFILLMENT_NODES,
  countReceivedLines,
  lineInWarehouse,
  litNodes,
  pendingLines,
  segmentShares,
  sharePercentLabel,
} from "./orderProgress";

function line(over: Partial<PortalOrderLine> = {}): PortalOrderLine {
  return {
    name_snapshot: "x", spec_text_snapshot: null, unit_code: "PCS", unit_label: "pcs",
    qty: "10.000", received_qty: "0.000", shipped_qty: "0.000", pending_qty: "10.000",
    in_warehouse_qty: "0.000", unit_price: "1.00", line_total: "10.00", sort_order: 1, ...over,
  };
}

function shipment(over: Partial<PortalShipment> = {}): PortalShipment {
  return {
    container_no: "C1", container_type: null, stage: "LOADED", vessel_name: null, voyage_no: null,
    customs_status: "NONE", declared_at: null, released_at: null, loaded_at: "2026-09-01T00:00:00Z",
    etd: null, atd: null, eta: null, port_of_loading: null, port_of_discharge: null, milestones: [],
    lines: [], ...over,
  };
}

describe("litNodes", () => {
  it("has one flag per node", () => {
    expect(litNodes({ status: "CONFIRMED", lines: [] }, null)).toHaveLength(FULFILLMENT_NODES.length);
  });

  it("without a container, node 2 follows order-level receipt and 3–6 stay dark", () => {
    const partly = [line({ received_qty: "10.000" }), line({ received_qty: "3.000" })];
    expect(litNodes({ status: "CONFIRMED", lines: partly }, null)).toEqual([true, false, false, false, false, false]);
    const all = [line({ received_qty: "10.000" }), line({ received_qty: "12.000" })];
    expect(litNodes({ status: "CONFIRMED", lines: all }, null)).toEqual([true, true, false, false, false, false]);
  });

  it("an empty line list never lights node 2 by vacuous truth", () => {
    expect(litNodes({ status: "CONFIRMED", lines: [] }, null)[1]).toBe(false);
  });

  it("with a container, node 2 lights because the container is loaded, even if other lines are not received", () => {
    const order = { status: "CONFIRMED", lines: [line({ received_qty: "10.000" }), line({ received_qty: "0.000" })] };
    expect(litNodes(order, shipment({ stage: "LOADED" }))).toEqual([true, true, true, false, false, false]);
  });

  it("nodes 4–6 only light on their own facts, never inferred from stage", () => {
    const order = { status: "CONFIRMED", lines: [line()] };
    const forced = shipment({ stage: "IN_TRANSIT", customs_status: "NONE", atd: "2026-09-05" });
    expect(litNodes(order, forced)).toEqual([true, true, true, false, true, false]);
    const arrived = shipment({
      stage: "ARRIVED", customs_status: "RELEASED", atd: "2026-09-05",
      milestones: [{ type: "ARRIVED", event_at: "2026-10-01", location: null }],
    });
    expect(litNodes(order, arrived)).toEqual([true, true, true, true, true, true]);
  });

  it("an unknown shipment stage does not light node 3", () => {
    expect(litNodes({ status: "CONFIRMED", lines: [line()] }, shipment({ stage: "WEIRD" as never }))[2]).toBe(false);
  });
});

describe("countReceivedLines", () => {
  it("counts lines whose received_qty >= qty using decimal string comparison", () => {
    expect(countReceivedLines([line({ received_qty: "10" }), line({ received_qty: "9.999" }), line({ received_qty: "10.000" })])).toBe(2);
  });
});

describe("pendingLines / lineInWarehouse", () => {
  it("keeps only lines with pending_qty > 0, in sort order", () => {
    const rows = [
      line({ sort_order: 3, pending_qty: "0.000" }),
      line({ sort_order: 2, pending_qty: "2.500" }),
      line({ sort_order: 1, pending_qty: "10.000" }),
    ];
    expect(pendingLines(rows).map((l) => l.sort_order)).toEqual([1, 2]);
  });

  it("treats missing or malformed pending_qty as not pending", () => {
    expect(pendingLines([line({ pending_qty: undefined as never }), line({ pending_qty: "abc" })])).toEqual([]);
  });

  it("a line is in warehouse when in_warehouse_qty >= pending_qty", () => {
    expect(lineInWarehouse(line({ pending_qty: "5.000", in_warehouse_qty: "5" }))).toBe(true);
    expect(lineInWarehouse(line({ pending_qty: "5.000", in_warehouse_qty: "4.999" }))).toBe(false);
  });
});

describe("segmentShares", () => {
  const seg = (over: Partial<PortalValueSegments> = {}): PortalValueSegments => ({
    arrived: "0.00", in_transit: "0.00", loaded: "0.00", in_warehouse: "0.00", not_received: "0.00", ...over,
  });

  it("returns five segments in display order with shares that sum to 1", () => {
    const shares = segmentShares(seg({ arrived: "45.00", loaded: "45.00", not_received: "10.00" }));
    expect(shares.map((s) => s.key)).toEqual(["arrived", "in_transit", "loaded", "in_warehouse", "not_received"]);
    expect(shares.map((s) => s.share)).toEqual([0.45, 0, 0.45, 0, 0.1]);
    expect(shares.reduce((a, s) => a + s.share, 0)).toBeCloseTo(1);
  });

  it("uses the sum of the five segments as the denominator, not total_amount", () => {
    const shares = segmentShares(seg({ in_warehouse: "30.00", not_received: "10.00" }));
    expect(shares.find((s) => s.key === "in_warehouse")?.share).toBeCloseTo(0.75);
  });

  it("all-zero segments give all-zero shares instead of NaN", () => {
    expect(segmentShares(seg()).map((s) => s.share)).toEqual([0, 0, 0, 0, 0]);
  });

  it("a malformed amount counts as zero", () => {
    const shares = segmentShares(seg({ arrived: "abc", loaded: "10.00" }));
    expect(shares.map((s) => s.share)).toEqual([0, 0, 1, 0, 0]);
  });
});

describe("sharePercentLabel", () => {
  it("rounds to whole percent", () => {
    expect(sharePercentLabel(0.456)).toBe("46%");
    expect(sharePercentLabel(1)).toBe("100%");
  });

  it("never shows 0% for a non-zero share", () => {
    expect(sharePercentLabel(0.004)).toBe("<1%");
    expect(sharePercentLabel(0.0099)).toBe("<1%");
    expect(sharePercentLabel(0)).toBe("0%");
  });
});
