"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { cn } from "@/lib/utils";
import type { CategoryTreeNode } from "@/lib/api/categories";

export interface SelectedCategory {
  /** 从 L1 到最深选中层的 code 列表，如 ["01", "01.002", "01.002.003"] */
  codes: string[];
}

export interface CategoryCascaderProps {
  value: SelectedCategory;
  onChange: (v: SelectedCategory) => void;
  /** 是否必填,展示提示用,不阻止操作 */
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export const EMPTY_CATEGORY: SelectedCategory = { codes: [] };

/** 取最深层选中的 code（即 codes 数组最后一个元素） */
export function getLeafCode(cat: SelectedCategory): string | null {
  return cat.codes.length > 0 ? cat.codes[cat.codes.length - 1] : null;
}

const SELECT_CLS = cn(
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
);

const LABEL_CLS = "text-sm font-medium text-slate-700";

const LEVEL_KEYS = ["level1", "level2", "level3", "level4"] as const;
const SELECT_KEYS = ["select_level1", "select_level2", "select_level3", "select_level4"] as const;

/**
 * 动态分类联动选择器，支持任意层级深度。
 *
 * 行为:
 * - 初次渲染 SWR 拉树,加载中所有 select disabled
 * - 任一级变更 → 清空该级以下所有选择
 * - 上级未选 → 下级 disabled
 * - 选中非叶子节点 → 自动出现下一级 select
 * - 选中叶子节点 → 不再出现新 select
 */
export function CategoryCascader({
  value,
  onChange,
  required,
  disabled,
  className,
}: CategoryCascaderProps) {
  const t = useTranslations("category");
  const { tree, isLoading, error } = useCategoryTree();

  // 计算每级的选项列表
  const levels = React.useMemo(() => {
    const result: { options: CategoryTreeNode[]; selectedCode: string | null; level: number }[] = [];
    let currentOptions = tree;
    for (let i = 0; i < value.codes.length; i++) {
      const code = value.codes[i];
      result.push({ options: currentOptions, selectedCode: code, level: i + 1 });
      const node = currentOptions.find((n) => n.code === code);
      if (node?.children?.length) {
        currentOptions = node.children;
      } else {
        // 叶子节点或无子节点，停止
        return result;
      }
    }
    // 还有下一级可选（当前选中的节点有子节点），追加空 select
    if (currentOptions.length > 0) {
      result.push({ options: currentOptions, selectedCode: null, level: value.codes.length + 1 });
    }
    return result;
  }, [tree, value.codes]);

  const baseDisabled = disabled || isLoading;

  const handleChange = React.useCallback(
    (levelIndex: number, code: string) => {
      if (code) {
        // 选中：保留前面的，设置当前，清空后面的
        const next = value.codes.slice(0, levelIndex);
        next.push(code);
        onChange({ codes: next });
      } else {
        // 清空当前级及以下
        onChange({ codes: value.codes.slice(0, levelIndex) });
      }
    },
    [value.codes, onChange]
  );

  if (error) {
    return (
      <div className={cn("text-sm text-red-600", className)}>
        {t("load_error")}: {error.message}
      </div>
    );
  }

  if (!isLoading && tree.length === 0) {
    return (
      <div className={cn("text-sm text-slate-500", className)}>
        {t("no_data")}
      </div>
    );
  }

  // 根据实际级数动态计算 grid 列数
  const gridCols = levels.length <= 1 ? "sm:grid-cols-1"
    : levels.length === 2 ? "sm:grid-cols-2"
    : levels.length === 3 ? "sm:grid-cols-3"
    : "sm:grid-cols-4";

  return (
    <div className={cn("grid grid-cols-1 gap-3", gridCols, className)}>
      {levels.map(({ options, selectedCode, level }, idx) => {
        const labelKey = LEVEL_KEYS[level - 1] ?? null;
        const selectKey = SELECT_KEYS[level - 1] ?? null;
        const parentSelected = idx === 0 || value.codes[idx - 1];
        return (
          <div key={idx} className="space-y-1">
            <label className={LABEL_CLS}>
              {labelKey ? t(labelKey) : `${t("level_prefix")} ${level}`}
              {required && <span className="ml-1 text-red-500">*</span>}
            </label>
            <select
              className={SELECT_CLS}
              value={selectedCode ?? ""}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={baseDisabled || !parentSelected}
            >
              <option value="">
                {idx === 0 && isLoading
                  ? t("loading")
                  : parentSelected
                    ? (selectKey ? t(selectKey) : t("select_parent_first"))
                    : t("select_parent_first")}
              </option>
              {options.map((n) => (
                <option key={n.code} value={n.code}>
                  {n.name}
                </option>
              ))}
            </select>
          </div>
        );
      })}
    </div>
  );
}
