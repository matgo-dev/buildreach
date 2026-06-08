"use client";

import React from "react";
import { useLocale, useTranslations } from "next-intl";
import type { PriceTier } from "@/lib/api/products";
import { formatCurrency } from "@/lib/formatters";

interface PriceTiersProps {
  tiers: PriceTier[];
  unit: string;
  /** 当前输入数量,用于高亮匹配行 */
  quantity: number | null;
}

/** 根据数量匹配阶梯价,返回匹配的 tier 或 null */
export function matchTier(tiers: PriceTier[], qty: number): PriceTier | null {
  if (tiers.length === 0 || qty <= 0) return null;
  // 按 min_qty 升序排好
  const sorted = [...tiers].sort((a, b) => a.min_qty - b.min_qty);
  for (const tier of sorted) {
    const inRange = qty >= tier.min_qty && (tier.max_qty === null || qty <= tier.max_qty);
    if (inRange) return tier;
  }
  return null;
}

export function PriceTiers({ tiers, unit, quantity }: PriceTiersProps) {
  const t = useTranslations("mall");
  const locale = useLocale();

  if (tiers.length === 0) return null;

  const sorted = [...tiers].sort((a, b) => a.min_qty - b.min_qty);
  const unitLabel = t(`unit_${unit}` as Parameters<typeof t>[0]);
  const matchedTier = quantity !== null && quantity > 0 ? matchTier(tiers, quantity) : null;

  return (
    <div className="mt-3">
      <div className="mb-1.5 text-xs font-semibold text-gray-600">
        {t("detail.volumePricing")}
      </div>
      <div className="space-y-0.5">
        {sorted.map((tier) => {
          const isActive = matchedTier?.id === tier.id;
          const rangeText = tier.max_qty
            ? `${tier.min_qty} - ${tier.max_qty} ${unitLabel}`
            : `${tier.min_qty}+ ${unitLabel}`;

          return (
            <div
              key={tier.id}
              className={`flex items-center rounded px-2 py-1.5 text-xs ${
                isActive
                  ? "bg-green-50 font-semibold"
                  : "border-b border-gray-50"
              }`}
            >
              <span className={`w-32 ${isActive ? "text-green-700" : "text-gray-500"}`}>
                {rangeText}
                {isActive && " \u2713"}
              </span>
              <span className={isActive ? "text-green-700" : "text-[#0D4D4D] font-semibold"}>
                {formatCurrency(tier.unit_price, tier.currency, locale, {
                  maximumFractionDigits: 2,
                })}{" "}
                / {unitLabel}
              </span>
              {isActive && (
                <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-bold text-green-700">
                  Best Price
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
