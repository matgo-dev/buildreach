"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, X } from "lucide-react";

import type { CategoryTreeNode } from "@/lib/api/categories";

interface Props {
  tree: CategoryTreeNode[];
  /** 当前选中的 category code（任意层级） */
  value: string;
  onChange: (code: string) => void;
  placeholder?: string;
}

/**
 * 级联品类选择器（单按钮 + 悬浮多列面板）。
 * 点击触发按钮弹出最多三列面板，hover 展开下级，点击叶子节点确认选择。
 */
export function CategoryCascaderDropdown({ tree, value, onChange, placeholder = "All" }: Props) {
  const [open, setOpen] = useState(false);
  const [hoverL1, setHoverL1] = useState<string | null>(null);
  const [hoverL2, setHoverL2] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // 构建 code → node 映射用于显示选中路径
  const codeMap = useMemo(() => {
    const map = new Map<string, CategoryTreeNode>();
    function walk(nodes: CategoryTreeNode[]) {
      for (const n of nodes) {
        map.set(n.code, n);
        if (n.children?.length) walk(n.children);
      }
    }
    walk(tree);
    return map;
  }, [tree]);

  // 解析选中值的完整路径
  const selectedLabel = useMemo(() => {
    if (!value) return "";
    const parts = value.split(".");
    const labels: string[] = [];
    for (let i = 1; i <= parts.length; i++) {
      const code = parts.slice(0, i).join(".");
      const node = codeMap.get(code);
      if (node) labels.push(node.name);
    }
    return labels.join(" / ");
  }, [value, codeMap]);

  const l2Options = useMemo(
    () => (hoverL1 ? tree.find((n) => n.code === hoverL1)?.children ?? [] : []),
    [tree, hoverL1]
  );
  const l3Options = useMemo(
    () => (hoverL2 ? l2Options.find((n) => n.code === hoverL2)?.children ?? [] : []),
    [l2Options, hoverL2]
  );

  const handleSelect = useCallback(
    (code: string, isLeaf: boolean) => {
      if (!isLeaf) return; // 非叶子不可选中,继续展开
      onChange(code);
      setOpen(false);
    },
    [onChange]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange("");
      setOpen(false);
    },
    [onChange]
  );

  return (
    <div ref={containerRef} className="relative">
      {/* 触发按钮 */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 hover:border-slate-300 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
      >
        <span className={`max-w-[200px] truncate ${value ? "text-slate-900" : "text-slate-400"}`}>
          {selectedLabel || placeholder}
        </span>
        {value ? (
          <X className="h-3.5 w-3.5 shrink-0 text-slate-400 hover:text-slate-600" onClick={handleClear} />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        )}
      </button>

      {/* 浮层面板 */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 flex rounded-lg border border-slate-200 bg-white shadow-lg">
          {/* L1 列 */}
          <ul className="max-h-[320px] w-[180px] overflow-y-auto border-r border-slate-100 py-1">
            {tree.map((n) => {
              const active = hoverL1 === n.code;
              return (
                <li
                  key={n.code}
                  onMouseEnter={() => { setHoverL1(n.code); setHoverL2(null); }}
                  onClick={() => handleSelect(n.code, n.is_leaf)}
                  className={`flex cursor-pointer items-center justify-between px-3 py-2 text-sm transition-colors ${
                    active ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <span className="truncate">{n.name}</span>
                  {!n.is_leaf && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
                </li>
              );
            })}
          </ul>

          {/* L2 列 */}
          {l2Options.length > 0 && (
            <ul className="max-h-[320px] w-[180px] overflow-y-auto border-r border-slate-100 py-1">
              {l2Options.map((n) => {
                const active = hoverL2 === n.code;
                return (
                  <li
                    key={n.code}
                    onMouseEnter={() => setHoverL2(n.code)}
                    onClick={() => handleSelect(n.code, n.is_leaf)}
                    className={`flex cursor-pointer items-center justify-between px-3 py-2 text-sm transition-colors ${
                      active ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <span className="truncate">{n.name}</span>
                    {!n.is_leaf && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
                  </li>
                );
              })}
            </ul>
          )}

          {/* L3+ 列 */}
          {l3Options.length > 0 && (
            <ul className="max-h-[320px] w-[180px] overflow-y-auto py-1">
              {l3Options.map((n) => (
                <li
                  key={n.code}
                  onClick={() => handleSelect(n.code, n.is_leaf)}
                  className={`cursor-pointer truncate px-3 py-2 text-sm transition-colors ${
                    n.is_leaf
                      ? "text-slate-700 hover:bg-blue-50 hover:text-blue-700"
                      : "text-slate-400 cursor-not-allowed"
                  }`}
                >
                  {n.name}
                  {!n.is_leaf && <span className="ml-1 text-xs text-slate-300">▸</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
