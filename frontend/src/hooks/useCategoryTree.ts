"use client";

import { useLocale } from "next-intl";
import useSWR from "swr";

import { categoriesApi, type CategoryTreeNode } from "@/lib/api/categories";

/**
 * 拉取商品分类三层嵌套树(GET /api/v1/categories/tree)。
 *
 * SWR key 包含 locale,语言切换时自动重新请求以获取对应语言的 name。
 */
export function useCategoryTree() {
  const locale = useLocale();
  const { data, error, isLoading, mutate } = useSWR<CategoryTreeNode[]>(
    `/api/v1/categories/tree?locale=${locale}`,
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
