"use client";

import { useState } from "react";
import type { PriceTierInput } from "@/lib/api/operatorProducts";
import { Button } from "@/components/ui/button";

interface Props {
  tiers: PriceTierInput[];
  moq: number;
  currency: string;
  onConfirm: (tiers: PriceTierInput[]) => void;
  onCancel: () => void;
  t: (key: string) => string;
}

function createEmptyTier(currency: string, moq?: number): PriceTierInput {
  return {
    min_qty: moq ?? 1,
    max_qty: null,
    unit_price: 0,
    currency,
  };
}

export function PriceTierModal({ tiers: initial, moq, currency, onConfirm, onCancel, t }: Props) {
  const [tiers, setTiers] = useState<PriceTierInput[]>(() => {
    if (initial.length > 0) {
      // 首档 min_qty 强制同步 MOQ
      return initial.map((tier, i) => i === 0 ? { ...tier, min_qty: moq } : tier);
    }
    return [createEmptyTier(currency, moq)];
  });

  const update = (idx: number, patch: Partial<PriceTierInput>) => {
    // 首档 min_qty 锁定为 MOQ，不允许修改
    if (idx === 0 && "min_qty" in patch) delete patch.min_qty;
    setTiers((prev) => prev.map((tier, i) => (i === idx ? { ...tier, ...patch } : tier)));
  };

  const addTier = () => {
    const last = tiers[tiers.length - 1];
    const nextMin = (last?.max_qty ?? moq) + 1;
    setTiers([...tiers, { ...createEmptyTier(currency), min_qty: nextMin }]);
  };

  const removeTier = (idx: number) => {
    setTiers((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-base font-semibold text-slate-800">{t("tier_title")}</h3>

        <div className="mb-3 space-y-2">
          {tiers.map((tier, idx) => (
            <div key={idx} className="flex items-end gap-2 rounded-md bg-slate-50 p-3">
              <div className="flex-1">
                <label className="text-xs text-slate-500">{t("tier_min_qty")}{idx === 0 && <span className="text-slate-400 ml-1">(= MOQ)</span>}</label>
                <input
                  type="number"
                  min="1"
                  className={`mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs ${idx === 0 ? "bg-slate-100 text-slate-500 cursor-not-allowed" : ""}`}
                  value={tier.min_qty}
                  readOnly={idx === 0}
                  onChange={(e) => update(idx, { min_qty: Number(e.target.value) || 1 })}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-500">{t("tier_max_qty")}</label>
                <input
                  type="number"
                  min="1"
                  className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                  value={tier.max_qty ?? ""}
                  placeholder="∞"
                  onChange={(e) => {
                    const val = e.target.value;
                    update(idx, { max_qty: val ? Number(val) : null });
                  }}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-500">{t("tier_unit_price")} ({currency})</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs"
                  value={tier.unit_price || ""}
                  onChange={(e) => update(idx, { unit_price: Number(e.target.value) || 0 })}
                />
              </div>
              <button
                type="button"
                onClick={() => removeTier(idx)}
                className="mb-0.5 text-xs text-red-500 hover:text-red-700"
                disabled={tiers.length <= 1}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addTier} className="mb-4 text-xs text-blue-600 hover:text-blue-800">
          {t("tier_add")}
        </button>

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            {t("tier_cancel")}
          </Button>
          <Button size="sm" onClick={() => onConfirm(tiers)}>
            {t("tier_confirm")}
          </Button>
        </div>
      </div>
    </div>
  );
}
