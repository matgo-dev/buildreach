"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Clock, X } from "lucide-react";
import { useLocale } from "next-intl";
import useSWR from "swr";

import { getRecentViews, removeRecentView, type RecentViewProduct } from "@/lib/api/buyerEvents";

/**
 * 最近浏览商品横栏 — 商城列表页顶部。
 * 无数据时 return null，不占空间。
 */
export function RecentViews() {
  const t = useTranslations("mall");
  const locale = useLocale();

  const { data: items, mutate } = useSWR<RecentViewProduct[]>(
    `buyer-recent-views-${locale}`,
    () => getRecentViews(8),
    { revalidateOnFocus: true, dedupingInterval: 30_000 },
  );

  if (!items || items.length === 0) return null;

  const handleRemove = async (e: React.MouseEvent, productId: number) => {
    // 阻止冒泡到 Link
    e.preventDefault();
    e.stopPropagation();
    // 乐观更新：立即从列表移除
    mutate(
      items.filter((i) => i.id !== productId),
      false,
    );
    try {
      await removeRecentView(productId);
      mutate();
    } catch {
      // 失败回滚
      mutate();
    }
  };

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-600">
        <Clock className="h-4 w-4" />
        <span>{t("recentViews")}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pt-2 pb-1 pr-2 scrollbar-thin">
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/mall/products/${item.id}`}
            className="group relative flex-shrink-0"
          >
            <div className="w-28 rounded-md border border-gray-100 bg-gray-50 p-2 transition-shadow hover:shadow-md">
              {/* 删除按钮 — 悬浮显示 */}
              <button
                onClick={(e) => handleRemove(e, item.id)}
                className="absolute -right-1.5 -top-1.5 z-10 hidden h-5 w-5 items-center justify-center rounded-full bg-gray-400 text-white shadow-sm transition-colors hover:bg-red-500 group-hover:flex"
                title={t("removeRecentView")}
              >
                <X className="h-3 w-3" />
              </button>
              {/* 商品图 */}
              <div className="mb-1.5 aspect-square w-full overflow-hidden rounded bg-white">
                {item.main_image ? (
                  <img
                    src={item.main_image}
                    alt={item.name}
                    className="h-full w-full object-contain"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-gray-300">
                    <span className="text-2xl">📦</span>
                  </div>
                )}
              </div>
              {/* 商品名 */}
              <p className="truncate text-xs text-gray-700 group-hover:text-teal-700">
                {item.name}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
