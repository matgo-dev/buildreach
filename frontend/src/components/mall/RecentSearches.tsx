"use client";

import { useTranslations } from "next-intl";
import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import useSWR from "swr";

import { getRecentSearches, clearRecentSearches } from "@/lib/api/buyerEvents";

interface Props {
  /** 搜索框是否聚焦 */
  visible: boolean;
  /** 选择某个搜索词 */
  onSelect: (keyword: string) => void;
  /** 面板外点击关闭 */
  onClose: () => void;
}

/**
 * 最近搜索下拉面板 — 搜索框聚焦时弹出。
 * 无搜索记录时不渲染。直接显示最多 10 条。
 */
export function RecentSearches({ visible, onSelect, onClose }: Props) {
  const t = useTranslations("mall");
  const panelRef = useRef<HTMLDivElement>(null);

  const { data: keywords, mutate } = useSWR<string[]>(
    visible ? "buyer-recent-searches" : null,
    () => getRecentSearches(10),
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  // 点击面板外关闭
  useEffect(() => {
    if (!visible) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // 延迟绑定，避免 focus 时的 click 立刻触发
    const timer = setTimeout(() => document.addEventListener("mousedown", handler), 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handler);
    };
  }, [visible, onClose]);

  const handleClear = useCallback(async () => {
    await clearRecentSearches();
    await mutate([], false);
    onClose();
  }, [mutate, onClose]);

  if (!visible || !keywords || keywords.length === 0) return null;

  return (
    <div
      ref={panelRef}
      className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg"
    >
      {/* 标题行 */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
        <span className="text-sm font-medium text-gray-700">
          {t("recentSearches")}
        </span>
        <button
          type="button"
          onClick={handleClear}
          className="flex items-center gap-1 text-xs text-gray-400 transition-colors hover:text-red-500"
          title={t("clearSearchHistory")}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 关键词列表 */}
      <div className="py-1">
        {keywords.map((kw) => (
          <button
            key={kw}
            type="button"
            onMouseDown={(e) => {
              e.preventDefault(); // 阻止 blur 先于 click 触发
              onSelect(kw);
            }}
            className="block w-full px-4 py-2 text-left text-sm text-gray-600 transition-colors hover:bg-gray-50 hover:text-teal-700"
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  );
}
