"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Clock } from "lucide-react";
import useSWR from "swr";

import { getRecentViews, type RecentViewProduct } from "@/lib/api/buyerEvents";

/**
 * 最近浏览商品横栏 — 商城列表页顶部。
 * 无数据时 return null，不占空间。
 */
export function RecentViews() {
  const t = useTranslations("mall");

  const { data: items } = useSWR<RecentViewProduct[]>(
    "buyer-recent-views",
    () => getRecentViews(8),
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  if (!items || items.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-600">
        <Clock className="h-4 w-4" />
        <span>{t("recentViews")}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/mall/products/${item.id}`}
            className="group flex-shrink-0"
          >
            <div className="w-28 rounded-md border border-gray-100 bg-gray-50 p-2 transition-shadow hover:shadow-md">
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
