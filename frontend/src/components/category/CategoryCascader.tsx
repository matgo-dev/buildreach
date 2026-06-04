"use client";

import * as React from "react";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { cn } from "@/lib/utils";
import type { CategoryTreeNode } from "@/lib/api/categories";

export interface SelectedCategory {
  level1Code: string | null;
  level2Code: string | null;
  /** 叶子节点 code,业务关联用 */
  level3Code: string | null;
}

export interface CategoryCascaderProps {
  value: SelectedCategory;
  onChange: (v: SelectedCategory) => void;
  /** 是否必填,展示提示用,不阻止操作 */
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

const EMPTY: SelectedCategory = {
  level1Code: null,
  level2Code: null,
  level3Code: null,
};

const SELECT_CLS = cn(
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
);

const LABEL_CLS = "text-sm font-medium text-slate-700";

/**
 * 三级分类联动选择器(对齐 docs/商品三级分类-PRD-v1.0.md §6)。
 *
 * 行为:
 * - 初次渲染 SWR 拉树,加载中所有 select disabled
 * - L1 变更 → 清空 L2/L3,L2 下拉重算
 * - L2 变更 → 清空 L3,L3 下拉重算
 * - 上级未选 → 下级 disabled
 * - 数据为空 → 显示"暂无数据,请联系管理员"
 */
export function CategoryCascader({
  value,
  onChange,
  required,
  disabled,
  className,
}: CategoryCascaderProps) {
  const { tree, isLoading, error } = useCategoryTree();

  const level1Node = React.useMemo<CategoryTreeNode | undefined>(
    () => tree.find((n) => n.code === value.level1Code),
    [tree, value.level1Code]
  );
  const level2Options = React.useMemo<CategoryTreeNode[]>(
    () => level1Node?.children ?? [],
    [level1Node]
  );

  const level2Node = React.useMemo<CategoryTreeNode | undefined>(
    () => level2Options.find((n) => n.code === value.level2Code),
    [level2Options, value.level2Code]
  );
  const level3Options = React.useMemo<CategoryTreeNode[]>(
    () => level2Node?.children ?? [],
    [level2Node]
  );

  const baseDisabled = disabled || isLoading;

  const handleL1 = (code: string) => {
    onChange({
      level1Code: code || null,
      level2Code: null,
      level3Code: null,
    });
  };
  const handleL2 = (code: string) => {
    onChange({
      level1Code: value.level1Code,
      level2Code: code || null,
      level3Code: null,
    });
  };
  const handleL3 = (code: string) => {
    onChange({
      level1Code: value.level1Code,
      level2Code: value.level2Code,
      level3Code: code || null,
    });
  };

  if (error) {
    return (
      <div className={cn("text-sm text-red-600", className)}>
        加载分类失败:{error.message}
      </div>
    );
  }

  if (!isLoading && tree.length === 0) {
    return (
      <div className={cn("text-sm text-slate-500", className)}>
        暂无分类数据,请联系管理员
      </div>
    );
  }

  return (
    <div className={cn("grid grid-cols-1 gap-3 sm:grid-cols-3", className)}>
      <div className="space-y-1">
        <label className={LABEL_CLS}>
          一级分类{required && <span className="ml-1 text-red-500">*</span>}
        </label>
        <select
          className={SELECT_CLS}
          value={value.level1Code ?? ""}
          onChange={(e) => handleL1(e.target.value)}
          disabled={baseDisabled}
        >
          <option value="">{isLoading ? "加载中…" : "请选择一级"}</option>
          {tree.map((n) => (
            <option key={n.code} value={n.code}>
              {n.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className={LABEL_CLS}>
          二级分类{required && <span className="ml-1 text-red-500">*</span>}
        </label>
        <select
          className={SELECT_CLS}
          value={value.level2Code ?? ""}
          onChange={(e) => handleL2(e.target.value)}
          disabled={baseDisabled || !value.level1Code}
        >
          <option value="">
            {value.level1Code ? "请选择二级" : "请先选上级"}
          </option>
          {level2Options.map((n) => (
            <option key={n.code} value={n.code}>
              {n.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className={LABEL_CLS}>
          三级分类{required && <span className="ml-1 text-red-500">*</span>}
        </label>
        <select
          className={SELECT_CLS}
          value={value.level3Code ?? ""}
          onChange={(e) => handleL3(e.target.value)}
          disabled={baseDisabled || !value.level2Code}
        >
          <option value="">
            {value.level2Code ? "请选择三级" : "请先选上级"}
          </option>
          {level3Options.map((n) => (
            <option key={n.code} value={n.code}>
              {n.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export const EMPTY_CATEGORY: SelectedCategory = EMPTY;
