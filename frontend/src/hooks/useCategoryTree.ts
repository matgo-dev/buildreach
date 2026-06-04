"use client";

import useSWR from "swr";

import { categoriesApi, type CategoryTreeNode } from "@/lib/api/categories";

/**
 * 拉取商品分类三层嵌套树(GET /api/v1/categories/tree)。
 *
 * 全量数据 < 2000 条,一次拉完缓存到 SWR;数据变更频率极低,无需自动刷新。
 */
export function useCategoryTree() {
  const { data, error, isLoading, mutate } = useSWR<CategoryTreeNode[]>(
    "/api/v1/categories/tree",
    () => categoriesApi.tree(),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
    }
  );

  return {
    tree: data ?? [],
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
