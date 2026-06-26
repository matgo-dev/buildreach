"use client";

import React, { useState, useRef, useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { ChevronDown, MessageCircle } from "lucide-react";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { useWhatsApp } from "@/hooks/useWhatsApp";

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
 * 获取某一级品类的同级节点列表（用于下拉切换）。
 * level 0 = 一级品类（tree 根节点），level 1 = 二级，以此类推。
 */
function getSiblings(
  tree: CategoryTreeNode[],
  path: { code: string; name: string }[],
  level: number,
): { code: string; name: string }[] {
  if (level === 0) return tree.map((n) => ({ code: n.code, name: n.name }));
  // 找到 path[level-1] 对应的父节点
  let nodes = tree;
  for (let i = 0; i < level; i++) {
    const parent = nodes.find((n) => n.code === path[i].code);
    if (!parent?.children) return [];
    nodes = parent.children;
  }
  return nodes.map((n) => ({ code: n.code, name: n.name }));
}

/** 单个面包屑节点 — 悬浮展开多列网格面板 */
function CrumbDropdown({
  crumb,
  siblings,
  onSelect,
}: {
  crumb: { code: string; name: string };
  siblings: { code: string; name: string }[];
  onSelect: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const handleEnter = () => {
    clearTimeout(timerRef.current);
    setOpen(true);
  };
  const handleLeave = () => {
    timerRef.current = setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // 移动端2列，桌面端根据数量：<=6 单列，<=15 三列，>15 五列
  const cols = siblings.length <= 6 ? 1 : siblings.length <= 15 ? 3 : 5;
  const desktopGrid =
    cols === 1 ? "sm:grid-cols-1 sm:w-48" :
    cols === 3 ? "sm:grid-cols-3 sm:w-[28rem]" :
    "sm:grid-cols-5 sm:w-[42rem]";

  return (
    <div
      ref={ref}
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-0.5 rounded-md border border-gray-200 bg-white px-2 py-0.5 text-[12px] text-gray-700 hover:border-teal-400 hover:text-teal-700 transition-colors h-[28px]"
      >
        <span className="max-w-[120px] truncate">{crumb.name}</span>
        <ChevronDown className={`h-3.5 w-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && siblings.length > 0 && (
        <div className={`absolute left-0 top-full z-50 mt-1 grid grid-cols-2 w-[calc(100vw-2rem)] ${desktopGrid} gap-0 rounded-lg border border-gray-200 bg-white shadow-lg max-h-80 overflow-y-auto`}>
          {siblings.map((s) => (
            <button
              key={s.code}
              onClick={() => {
                onSelect(s.code);
                setOpen(false);
              }}
              className={`text-left px-3 py-2 text-[12px] transition-colors ${
                s.code === crumb.code
                  ? "bg-teal-50 text-teal-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50 hover:text-teal-700"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * 品类面包屑导航组件（鑫方盛风格）。
 *
 * 全部结果 / [一级品类 ▼] / [二级品类 ▼] / [三级品类 ▼]
 * 每级品类可悬浮下拉切换同级品类，选中后截断后续层级。
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
  const router = useRouter();
  const t = useTranslations("mall");
  const { buildLink, configured } = useWhatsApp();

  const crumbs = categoryCode ? buildCategoryPath(categoryTree, categoryCode) : [];

  // 选中某一级品类后，截断后续层级，跳转到该品类
  const handleSelect = (code: string) => {
    router.replace(`/${locale}/mall?cat=${code}`, { scroll: false });
  };

  return (
    <nav aria-label="Breadcrumb">
      <div className="flex flex-wrap items-center gap-2 text-[12px] py-1">
        <span className="text-gray-500 shrink-0">
          {t("allResults")}
        </span>

        {crumbs.map((crumb, idx) => {
          const siblings = getSiblings(categoryTree, crumbs, idx);
          return (
            <React.Fragment key={crumb.code}>
              <span className="text-gray-300">/</span>
              <CrumbDropdown
                crumb={crumb}
                siblings={siblings}
                onSelect={handleSelect}
              />
            </React.Fragment>
          );
        })}

        {tail && (
          <>
            <span className="text-gray-300">/</span>
            <span className="max-w-[200px] truncate text-[12px] font-medium text-gray-700">
              {tail}
            </span>
          </>
        )}

        {/* 客服入口 — 仅列表页显示，详情页(有tail)不显示 */}
        {configured && !tail && (
          <div className="ml-4 flex items-center gap-2 shrink-0">
            <span className="text-[12px] text-amber-500 hidden sm:inline">{t("cantFindHint")}</span>
            <a
              href={buildLink() || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-whatsapp px-3 py-1 text-[12px] font-medium text-white hover:bg-[#20bd5a] transition-colors h-[28px]"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              {t("contactService")}
            </a>
          </div>
        )}
      </div>
    </nav>
  );
}
