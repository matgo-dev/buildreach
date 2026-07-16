"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Loader2, PackageOpen } from "lucide-react";

import type { HomeFloorCategory, ProductPublic } from "@/lib/api/products";
import { imageUrl } from "@/lib/env";
import { ProductCardCompact } from "./ProductCardCompact";
import { MOCK_FLOOR_PRODUCTS } from "./floorMockData";

/** 楼层配置项 */
export interface FloorConfig {
  id: string;             // DOM id，供电梯锚点用
  nameKey: string;        // i18n key
  bgImage: string;        // 左区背景图相对 key（/static/floors/xxx.webp，由后端 serve uploads 卷,渲染时拼 API base）
}

export function CategoryFloorSection({
  config,
  products: realProducts,
  categories,
  isLoading,
}: {
  config: FloorConfig;
  products?: ProductPublic[];
  categories?: HomeFloorCategory[];
  isLoading: boolean;
}) {
  const t = useTranslations("mall");
  const router = useRouter();

  // 有真实楼层数据就展示真实数据；只有 API 为空/失败时才用 Mock 占位。
  // mock 按楼层 id 匹配（不依赖品类 code，初始化数据后 code 可能变化）
  const mockProducts = (MOCK_FLOOR_PRODUCTS[config.id] ?? []) as ProductPublic[];
  const products: ProductPublic[] = realProducts && realProducts.length > 0 ? realProducts : mockProducts;
  const navCategories = categories ?? [];

  return (
    <section
      id={config.id}
      className="rounded-xl overflow-hidden border border-line bg-white"
      style={{ boxShadow: "0 1px 4px rgba(16,36,65,.05)" }}
    >
      {/* ── 移动端品类标题横条(md 以上由左区背景图代替) ── */}
      <div className="md:hidden px-4 py-3 text-white font-bold text-sm bg-gray-700">
        {t(config.nameKey)}
      </div>

      <div className="flex min-h-0">
        {/* ── 左区：独立圆角背景卡，图片铺满并随圆角裁切 ── */}
        <div
          className="relative hidden w-[220px] shrink-0 self-stretch overflow-hidden rounded-xl bg-gray-700 bg-no-repeat md:flex md:flex-col"
          style={{
            backgroundImage: `url(${imageUrl(config.bgImage)})`,
            backgroundPosition: "center center",
            backgroundSize: "108% 108%",
          }}
        >
          {/* 半透明遮罩保证文字可读 —— 祖母绿色调统一各楼层卡片(呼应品牌绿) */}
          <div className="absolute inset-0 bg-gradient-to-b from-teal-950/80 via-teal-900/55 to-teal-900/25" />

          {/* 文字叠在遮罩上 */}
          <div className="relative z-10 p-5 flex-1 flex flex-col">
            <h3 className="mb-5 text-xl font-black leading-snug text-white">
              {t(config.nameKey)}
            </h3>

            {navCategories.length > 0 && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-4">
                {navCategories.slice(0, 10).map((category) => (
                  <button
                    key={category.code}
                    onClick={() => router.push(`/mall?cat=${category.code}`)}
                    className="truncate text-left text-[13px] font-bold leading-relaxed text-white/90 transition-colors hover:text-white hover:underline"
                  >
                    {category.name}
                  </button>
                ))}
              </div>
            )}
          </div>
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
