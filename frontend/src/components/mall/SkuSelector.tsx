"use client";

import React, { useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import type { SkuPublic } from "@/lib/api/products";

// ---- 类型 ----

/** 一个选择器维度 */
export interface SkuDimension {
  key: string;          // "color" | "material" | attr_key
  label: string;        // 展示名
  values: string[];     // 所有可选值(去重、有序)
  sortOrder: number;    // 排序权重
}

/** 选中的维度组合 */
export type DimensionSelection = Record<string, string>;

interface SkuSelectorProps {
  skus: SkuPublic[];
  selection: DimensionSelection;
  onSelectionChange: (sel: DimensionSelection) => void;
}

// ---- 核心算法 ----

/**
 * 从 active SKU 列表中提取差异维度。
 * 规则:某属性 key 的不同值数量 > 1 才成为可选维度。
 * 排序: color(0) > material(1) > 其他按 sort_order。
 */
export function extractDimensions(skus: SkuPublic[]): SkuDimension[] {
  if (skus.length === 0) return [];

  // 收集每个属性 key 的所有值
  const valueMap = new Map<string, { values: Set<string>; label: string; sortOrder: number }>();

  const ensureKey = (key: string, label: string, sortOrder: number) => {
    if (!valueMap.has(key)) {
      valueMap.set(key, { values: new Set(), label, sortOrder });
    }
  };

  for (const sku of skus) {
    // 直接字段: color, material
    if (sku.color) {
      ensureKey("color", "Color", 0);
      valueMap.get("color")!.values.add(sku.color);
    }
    if (sku.material) {
      ensureKey("material", "Material", 1);
      valueMap.get("material")!.values.add(sku.material);
    }

    // SKU 级 attributes
    for (const attr of sku.attributes) {
      const key = attr.attr_key;
      const label = attr.display_name || key;
      const sortOrder = attr.sort_order + 100; // 排在直接字段后面
      ensureKey(key, label, sortOrder);
      valueMap.get(key)!.values.add(attr.attr_value);
    }
  }

  // 只保留值种类 > 1 的维度
  const dims: SkuDimension[] = [];
  for (const [key, info] of valueMap) {
    if (info.values.size > 1) {
      dims.push({
        key,
        label: info.label,
        values: Array.from(info.values),
        sortOrder: info.sortOrder,
      });
    }
  }

  dims.sort((a, b) => a.sortOrder - b.sortOrder);
  return dims;
}

/** 获取 SKU 在某个维度上的值 */
function getSkuDimensionValue(sku: SkuPublic, dimKey: string): string | null {
  if (dimKey === "color") return sku.color || null;
  if (dimKey === "material") return sku.material || null;
  const attr = sku.attributes.find((a) => a.attr_key === dimKey);
  return attr?.attr_value || null;
}

/** 根据当前选中的维度组合定位唯一 SKU。
 *  部分选择时，如果已选维度只匹配到 1 个 SKU，也直接返回（不要求全选）。
 */
export function locateSku(
  skus: SkuPublic[],
  dimensions: SkuDimension[],
  selection: DimensionSelection
): SkuPublic | null {
  if (dimensions.length === 0 && skus.length > 0) {
    // 无差异维度 → 返回 default 或第一个
    return skus.find((s) => s.is_default) || skus[0];
  }

  // 按已选维度过滤候选 SKU
  const selectedDims = dimensions.filter((d) => selection[d.key]);
  if (selectedDims.length === 0) return null;

  const candidates = skus.filter((sku) =>
    selectedDims.every((d) => getSkuDimensionValue(sku, d.key) === selection[d.key])
  );

  // 精确匹配 1 个 → 直接返回（即使未全选，只要组合唯一就定位）
  if (candidates.length === 1) return candidates[0];

  // 全选且匹配 → 返回
  const allSelected = dimensions.every((d) => selection[d.key]);
  if (allSelected && candidates.length > 0) return candidates[0];

  return null;
}

/** 从 is_default SKU 反推初始选中状态 */
export function getDefaultSelection(
  skus: SkuPublic[],
  dimensions: SkuDimension[]
): DimensionSelection {
  const defaultSku = skus.find((s) => s.is_default) || skus[0];
  if (!defaultSku) return {};

  const sel: DimensionSelection = {};
  for (const dim of dimensions) {
    const val = getSkuDimensionValue(defaultSku, dim.key);
    if (val) sel[dim.key] = val;
  }
  return sel;
}

/**
 * 判断某个维度值在当前选中组合下是否可用。
 * 逻辑:把该维度替换为目标值,其余维度保持不变,看是否存在匹配的 SKU。
 */
function isValueAvailable(
  skus: SkuPublic[],
  dimensions: SkuDimension[],
  selection: DimensionSelection,
  targetDimKey: string,
  targetValue: string
): boolean {
  return skus.some((sku) => {
    // 目标维度必须匹配
    if (getSkuDimensionValue(sku, targetDimKey) !== targetValue) return false;
    // 其余已选维度也必须匹配
    for (const dim of dimensions) {
      if (dim.key === targetDimKey) continue;
      const selectedVal = selection[dim.key];
      if (!selectedVal) continue;
      if (getSkuDimensionValue(sku, dim.key) !== selectedVal) return false;
    }
    return true;
  });
}

// ---- 组件 ----

export function SkuSelector({ skus, selection, onSelectionChange }: SkuSelectorProps) {
  const t = useTranslations("mall");
  const dimensions = useMemo(() => extractDimensions(skus), [skus]);

  const handleChipClick = useCallback(
    (dimKey: string, value: string) => {
      const next = { ...selection };
      // 再次点击同一值 → 取消选中
      if (next[dimKey] === value) {
        delete next[dimKey];
      } else {
        next[dimKey] = value;
      }
      onSelectionChange(next);
    },
    [selection, onSelectionChange]
  );

  if (dimensions.length === 0) return null;

  return (
    <div className="space-y-3">
      {dimensions.map((dim) => (
        <div key={dim.key}>
          <div className="mb-1.5 text-xs font-semibold text-gray-600">{dim.label}</div>
          <div className="flex flex-wrap gap-1.5">
            {dim.values.map((val) => {
              const isSelected = selection[dim.key] === val;
              const available = isValueAvailable(skus, dimensions, selection, dim.key, val);

              return (
                <button
                  key={val}
                  type="button"
                  disabled={!available}
                  onClick={() => handleChipClick(dim.key, val)}
                  className={`rounded-md border-[1.5px] px-3.5 py-1.5 text-xs transition-all ${
                    isSelected
                      ? "border-[#00505a] bg-[#e6f3f3] font-semibold text-[#00505a]"
                      : available
                        ? "border-gray-200 bg-white text-gray-600 hover:border-[#00505a] hover:text-[#00505a]"
                        : "cursor-not-allowed border-dashed border-gray-200 text-gray-400 opacity-40"
                  }`}
                  title={!available ? t("detail.unavailable") : undefined}
                >
                  {available && (
                    <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                  )}
                  {val}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
