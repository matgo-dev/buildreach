"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import useSWR from "swr";
import { Loader2, PackageOpen } from "lucide-react";

import { listProducts, type ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { ProductCardCompact } from "./ProductCardCompact";

/** 楼层配置项 */
export interface FloorConfig {
  id: string;             // DOM id，供电梯锚点用
  nameKey: string;        // i18n key (如 "floorToolsConsumables")
  categoryCode: string;   // L1 品类 code（如 "01"）
  gradient: string;       // 左区背景渐变
  bgImage: string;        // 背景图 URL
}

const FLOOR_PRODUCT_SIZE = 8;

/**
 * 单个品类楼层：左区(品类信息) + 右区(商品网格)。
 */
export function CategoryFloorSection({
  config,
  categoryTree,
}: {
  config: FloorConfig;
  categoryTree: CategoryTreeNode[];
}) {
  const t = useTranslations("mall");
  const router = useRouter();

  // 从品类树中找到该 L1 品类节点
  const l1Node = categoryTree.find((c) => c.code === config.categoryCode);
  const l2Children = l1Node?.children ?? [];

  // 拉取该品类下 8 个商品（精选优先 → 最新）
  const { data, isLoading } = useSWR(
    `floor-products-${config.categoryCode}`,
    async () => {
      // 先拉精选
      const featured = await listProducts({
        category_code: config.categoryCode,
        featured: true,
        size: FLOOR_PRODUCT_SIZE,
        sort: "newest",
      });
      if (featured.items.length >= FLOOR_PRODUCT_SIZE) {
        return featured.items.slice(0, FLOOR_PRODUCT_SIZE);
      }
      // 精选不足，补充非精选
      const rest = await listProducts({
        category_code: config.categoryCode,
        size: FLOOR_PRODUCT_SIZE - featured.items.length,
        sort: "newest",
      });
      // 去重合并
      const seenIds = new Set(featured.items.map((p) => p.id));
      const extra = rest.items.filter((p) => !seenIds.has(p.id));
      return [...featured.items, ...extra].slice(0, FLOOR_PRODUCT_SIZE);
    },
    { revalidateOnFocus: false },
  );

  const products: ProductPublic[] = data ?? [];

  return (
    <section
      id={config.id}
      className="rounded-xl overflow-hidden border border-line bg-white"
      style={{ boxShadow: "0 1px 4px rgba(16,36,65,.05)" }}
    >
      {/* ── 移动端品类标题横条（flex 外，仅小屏显示） ── */}
      <div
        className="md:hidden px-4 py-3 text-white font-bold text-sm"
        style={{ background: config.gradient }}
      >
        {t(config.nameKey)}
      </div>

      <div className="flex min-h-[280px] md:min-h-[360px]">
        {/* ── 左区：品类信息（仅 md+ 显示）—— 鑫方盛风格 ── */}
        <div
          className="hidden md:flex w-[220px] shrink-0 flex-col justify-between p-5 text-white relative overflow-hidden"
          style={{ background: config.gradient }}
        >
          <div className="relative z-10">
            {/* 品类名 */}
            <h3 className="text-xl font-black mb-4">
              {t(config.nameKey)}
            </h3>

            {/* L2 子分类链接（2列） */}
            {l2Children.length > 0 && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-2">
                {l2Children.slice(0, 10).map((l2) => (
                  <button
                    key={l2.code}
                    onClick={() => router.push(`/mall?cat=${l2.code}`)}
                    className="text-left text-[13px] font-medium text-white/90 hover:text-white hover:underline transition-colors truncate"
                  >
                    {l2.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 底部品类装饰图 — 鑫方盛风格，占左区下部 */}
          <div
            className="absolute bottom-0 left-0 right-0 h-[45%] bg-contain bg-bottom bg-no-repeat opacity-30"
            style={{ backgroundImage: `url(${config.bgImage})` }}
          />
        </div>

        {/* ── 右区：商品网格 ── */}
        <div className="flex-1 p-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-gray-300" />
            </div>
          ) : products.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-2">
              <PackageOpen className="w-10 h-10" />
              <p className="text-sm">{t("floorComingSoon")}</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {products.map((product) => (
                <ProductCardCompact key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
