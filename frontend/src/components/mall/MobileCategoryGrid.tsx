"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, ChevronUp, LayoutGrid } from "lucide-react";
import useSWR from "swr";
import Image from "next/image";

import { categoriesApi, type CategoryThumbnail } from "@/lib/api/categories";

const DEFAULT_VISIBLE = 10;

/**
 * 移动端品类宫格入口 — 仅 < lg 显示。
 * 默认展示 10 个热门品类，可展开查看全部。
 * 用品类下代表商品的真实图片做缩略图。
 */
export function MobileCategoryGrid() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("mall");
  const [expanded, setExpanded] = useState(false);

  const { data: categories } = useSWR<CategoryThumbnail[]>(
    `/api/v1/categories/thumbnails?locale=${locale}`,
    () => categoriesApi.thumbnails(),
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  );

  if (!categories || categories.length === 0) return null;

  const visible = expanded ? categories : categories.slice(0, DEFAULT_VISIBLE);
  const hasMore = categories.length > DEFAULT_VISIBLE;

  return (
    <div className="block lg:hidden mb-4">
      {/* 标题栏 */}
      <div className="flex items-center gap-1.5 px-1 mb-2">
        <LayoutGrid className="w-4 h-4 text-teal-700" />
        <span className="text-sm font-bold text-gray-800">{t("allCategories")}</span>
      </div>

      {/* 宫格 */}
      <div className="grid grid-cols-5 gap-1">
        {visible.map((cat) => (
          <button
            key={cat.code}
            onClick={() => router.push(`/${locale}/mall?cat=${cat.code}`)}
            className="flex flex-col items-center gap-1.5 py-2 px-1 rounded-lg transition-colors active:bg-teal-50"
          >
            <div className="w-12 h-12 rounded-lg bg-gray-50 border border-gray-100 overflow-hidden flex items-center justify-center">
              {cat.thumbnail ? (
                <Image
                  src={cat.thumbnail}
                  alt={cat.name}
                  width={48}
                  height={48}
                  className="w-full h-full object-contain"
                  unoptimized
                />
              ) : (
                <LayoutGrid className="w-5 h-5 text-gray-300" />
              )}
            </div>
            <span className="text-[11px] leading-tight text-gray-600 text-center line-clamp-2">
              {cat.name}
            </span>
          </button>
        ))}
      </div>

      {/* 展开/收起 */}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-center gap-1 w-full mt-1 py-1.5 text-xs text-teal-700 font-medium"
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
