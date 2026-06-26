"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, ChevronUp, LayoutGrid } from "lucide-react";

import { useCategoryTree } from "@/hooks/useCategoryTree";

const DEFAULT_VISIBLE = 10;

/**
 * 移动端品类入口 — 仅 < lg 显示。
 * 纯文字标签，默认两行(10个)，可展开查看全部。
 * 数据来自 category tree，不依赖额外 API。
 */
export function MobileCategoryGrid() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const { tree: categories, isLoading } = useCategoryTree();
  const [expanded, setExpanded] = useState(false);

  if (isLoading || categories.length === 0) return null;

  const visible = expanded ? categories : categories.slice(0, DEFAULT_VISIBLE);
  const hasMore = categories.length > DEFAULT_VISIBLE;

  return (
    <div className="block lg:hidden mb-4">
      {/* 标题栏 */}
      <div className="flex items-center gap-1.5 px-1 mb-2">
        <LayoutGrid className="w-4 h-4 text-teal-700" />
        <span className="text-sm font-bold text-gray-800">{t("allCategories")}</span>
      </div>

      {/* 标签网格 */}
      <div className="grid grid-cols-5 gap-1.5">
        {visible.map((cat) => (
          <button
            key={cat.code}
            onClick={() => router.push(`/${locale}/mall?cat=${cat.code}`)}
            className="py-2 px-1 rounded-lg bg-gray-50 border border-gray-100 text-[12px] text-gray-700 text-center leading-tight truncate transition-colors active:bg-teal-50 active:text-teal-800 active:border-teal-200"
          >
            {cat.name}
          </button>
        ))}
      </div>

      {/* 展开/收起 */}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-center gap-1 w-full mt-2 py-1.5 text-xs text-teal-700 font-medium"
        >
          {expanded ? (
            <>
              {t("collapseCategories")} <ChevronUp className="w-3.5 h-3.5" />
            </>
          ) : (
            <>
              {t("viewAllCategories")} ({categories.length}) <ChevronDown className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      )}
    </div>
  );
}
