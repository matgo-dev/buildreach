"use client";

import React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Home, ChevronRight } from "lucide-react";
import type { CategoryTreeNode } from "@/lib/api/categories";

/**
 * 从品类树中 DFS 查找目标 code 的完整路径。
 * 返回从根到目标节点的 { code, name } 数组。
 */
export function buildCategoryPath(
  tree: CategoryTreeNode[],
  categoryCode: string,
): { code: string; name: string }[] {
  const path: { code: string; name: string }[] = [];
  function dfs(nodes: CategoryTreeNode[]): boolean {
    for (const node of nodes) {
      path.push({ code: node.code, name: node.name });
      if (node.code === categoryCode) return true;
      if (node.children && dfs(node.children)) return true;
      path.pop();
    }
    return false;
  }
  dfs(tree);
  return path;
}

/**
 * 品类面包屑导航组件。
 *
 * @param categoryCode  当前品类 code（为空时不渲染）
 * @param categoryTree  品类嵌套树
 * @param tail          末尾文字（如商品名），不可点击
 */
export function CategoryBreadcrumb({
  categoryCode,
  categoryTree,
  tail,
}: {
  categoryCode: string;
  categoryTree: CategoryTreeNode[];
  tail?: string;
}) {
  const locale = useLocale();
  const t = useTranslations("mall");

  if (!categoryCode && !tail) return null;

  const crumbs = categoryCode ? buildCategoryPath(categoryTree, categoryCode) : [];

  // 没有有效路径且没有 tail，不渲染
  if (crumbs.length === 0 && !tail) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 text-xs text-gray-400"
    >
      <Link
        href={`/${locale}/mall`}
        className="flex items-center gap-1 text-[#00505a] transition-colors hover:underline"
      >
        <Home className="h-3 w-3" />
        <span>{t("home")}</span>
      </Link>

      {crumbs.map((crumb, idx) => {
        const isLast = idx === crumbs.length - 1 && !tail;
        return (
          <React.Fragment key={crumb.code}>
            <ChevronRight className="h-3 w-3 flex-shrink-0 text-gray-300" />
            {isLast ? (
              <span className="font-medium text-gray-600">{crumb.name}</span>
            ) : (
              <Link
                href={`/${locale}/mall?cat=${crumb.code}`}
                className="text-[#00505a] transition-colors hover:underline"
              >
                {crumb.name}
              </Link>
            )}
          </React.Fragment>
        );
      })}

      {tail && (
        <>
          <ChevronRight className="h-3 w-3 flex-shrink-0 text-gray-300" />
          <span className="max-w-[200px] truncate font-medium text-gray-700">
            {tail}
          </span>
        </>
      )}
    </nav>
  );
}
