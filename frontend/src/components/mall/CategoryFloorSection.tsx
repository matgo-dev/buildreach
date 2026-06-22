"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import useSWR from "swr";
import { Loader2, PackageOpen } from "lucide-react";

import { listProducts, type ProductPublic } from "@/lib/api/products";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { ProductCardCompact } from "./ProductCardCompact";
import { MOCK_FLOOR_PRODUCTS } from "./floorMockData";

/** 楼层配置项 */
export interface FloorConfig {
  id: string;             // DOM id，供电梯锚点用
  nameKey: string;        // i18n key
  categoryCode: string;   // L1 品类 code
  bgImage: string;        // 左区背景图 URL（竖长图，底部有产品实物）
}

const FLOOR_PRODUCT_SIZE = 8;

export function CategoryFloorSection({
  config,
  categoryTree,
}: {
  config: FloorConfig;
  categoryTree: CategoryTreeNode[];
}) {
  const t = useTranslations("mall");
  const router = useRouter();

  const l1Node = categoryTree.find((c) => c.code === config.categoryCode);
  const l2Children = l1Node?.children ?? [];

  const { data, isLoading } = useSWR(
    `floor-products-${config.categoryCode}`,
    async () => {
      try {
        const featured = await listProducts({
          category_code: config.categoryCode,
          featured: true,
          size: FLOOR_PRODUCT_SIZE,
          sort: "newest",
        });
        if (featured.items.length >= FLOOR_PRODUCT_SIZE) {
          return featured.items.slice(0, FLOOR_PRODUCT_SIZE);
        }
        const rest = await listProducts({
          category_code: config.categoryCode,
          size: FLOOR_PRODUCT_SIZE,
          sort: "newest",
        });
        const seenIds = new Set(featured.items.map((p) => p.id));
        const extra = rest.items.filter((p) => !seenIds.has(p.id));
        return [...featured.items, ...extra].slice(0, FLOOR_PRODUCT_SIZE);
      } catch {
        return []; // API 错误时返回空，由 Mock 兜底
      }
    },
    { revalidateOnFocus: false },
  );

  // 真实数据 >= 4 个才用真实数据，否则用 Mock（TODO: 数据入库后移除）
  const mockProducts = (MOCK_FLOOR_PRODUCTS[config.categoryCode] ?? []) as ProductPublic[];
  const products: ProductPublic[] = (data && data.length >= 4) ? data : mockProducts;

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
          className="relative hidden w-[220px] shrink-0 overflow-hidden rounded-xl bg-gray-700 bg-center bg-no-repeat md:flex md:flex-col"
          style={{
            backgroundImage: `url(${config.bgImage})`,
            backgroundSize: "auto 108%",
          }}
        >
          {/* 半透明遮罩保证文字可读 */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/55 via-black/35 to-black/15" />

          {/* 文字叠在遮罩上 */}
          <div className="relative z-10 p-5 flex-1 flex flex-col">
            <h3 className="text-xl font-black text-white mb-5">
              {t(config.nameKey)}
            </h3>

            {l2Children.length > 0 && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-3">
                {l2Children.slice(0, 10).map((l2) => (
                  <button
                    key={l2.code}
                    onClick={() => router.push(`/mall?cat=${l2.code}`)}
                    className="text-left text-[13px] font-bold text-white/90 hover:text-white hover:underline transition-colors truncate"
                  >
                    {l2.name}
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
