"use client";

import React, { useCallback } from "react";
import { useTranslations } from "next-intl";
import { Minus, Plus } from "lucide-react";

interface QuantityInputProps {
  value: number;
  onChange: (qty: number) => void;
  moq: number;
  unit: string;
}

export function QuantityInput({ value, onChange, moq, unit }: QuantityInputProps) {
  const t = useTranslations("mall");
  const unitLabel = t(`unit_${unit}` as Parameters<typeof t>[0]);
  const step = moq; // 步进 = MOQ
  const isBelowMoq = value < moq;

  const handleDecrement = useCallback(() => {
    const next = value - step;
    // 不低于 MOQ
    onChange(Math.max(next, moq));
  }, [value, step, moq, onChange]);

  const handleIncrement = useCallback(() => {
    onChange(value + step);
  }, [value, step, onChange]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value.replace(/\D/g, "");
      if (raw === "") {
        onChange(0);
        return;
      }
      onChange(parseInt(raw, 10));
    },
    [onChange]
  );

  // 失焦时修正:如果低于 MOQ 则纠正为 MOQ
  const handleBlur = useCallback(() => {
    if (value < moq) onChange(moq);
  }, [value, moq, onChange]);

  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-gray-600">
          {t("detail.quantity")}
        </span>
        <div
          className={`flex items-center overflow-hidden rounded-md border-[1.5px] ${
            isBelowMoq ? "border-red-400" : "border-gray-200"
          }`}
        >
          <button
            type="button"
            onClick={handleDecrement}
            disabled={value <= moq}
            className="flex h-9 w-8 items-center justify-center bg-gray-50 text-gray-500 transition-colors hover:bg-gray-200 disabled:opacity-30"
          >
            <Minus className="h-4 w-4" />
          </button>
          <input
            type="text"
            inputMode="numeric"
            value={value || ""}
            onChange={handleInputChange}
            onBlur={handleBlur}
            className="h-9 w-16 border-x border-gray-200 text-center text-sm font-semibold outline-none"
          />
          <button
            type="button"
            onClick={handleIncrement}
            className="flex h-9 w-8 items-center justify-center bg-gray-50 text-gray-500 transition-colors hover:bg-gray-200"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        <span className="text-[11px] text-gray-400">
          MOQ: {moq} {unitLabel} · Step: {moq}
        </span>
      </div>
      {isBelowMoq && (
        <p className="mt-1 text-xs text-red-500">
          {t("detail.moqWarning", { moq, unit: unitLabel })}
        </p>
      )}
    </div>
  );
}
