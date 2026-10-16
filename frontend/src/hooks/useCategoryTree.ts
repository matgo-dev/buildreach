"use client";

import { useLocale } from "next-intl";
import useSWR from "swr";

import { categoriesApi, type CategoryTreeNode } from "@/lib/api/categories";

/**
 * 拉取商品分类嵌套树 — 两阶段加载策略。
 *
 * 阶段1: 请求 max_depth=2（L1+L2），响应小、渲染快
 * 阶段2: 后台静默加载完整树（含 L3+L4），加载完无缝替换
 *
 * 悬浮子分类面板用完整树数据渲染，首屏不阻塞。
 */
export function useCategoryTree() {
  const locale = useLocale();

  // 阶段1: L1+L2 浅层树（首屏快速渲染）
  const shallow = useSWR<CategoryTreeNode[]>(
    `/api/v1/categories/tree?max_depth=2&locale=${locale}`,
    () => categoriesApi.tree({ max_depth: 2 }),
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  // 阶段2: 完整树（后台静默加载，用于悬浮面板）
  const full = useSWR<CategoryTreeNode[]>(
    `/api/v1/categories/tree?locale=${locale}`,
    () => categoriesApi.tree(),
    { revalidateOnFocus: false, revalidateIfStale: false },
  );

  // 优先用完整树，未就绪时回退到浅层树
  const tree = full.data ?? shallow.data ?? [];
  const isLoading = shallow.isLoading;
  const error = shallow.error && full.error ? shallow.error : undefined;

  return {
    tree,
    isLoading,
    error: error as Error | undefined,
    refresh: () => { shallow.mutate(); full.mutate(); },
  };
}
