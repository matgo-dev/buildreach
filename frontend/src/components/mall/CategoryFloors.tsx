"use client";

import useSWR from "swr";

import { listHomeFloorProducts } from "@/lib/api/products";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * 楼层品类映射由后端按 name_zh 路径解析，前端只负责展示。
 * bgImage 走后端 /static/floors/*.webp（图片存 uploads/floors 卷，换图替换文件即可，免部署）。
 * 楼层数量/文件名固定(跟一级类目绑定)，只有图片内容会偶尔换，故不上 DB。
 *
 * 生产前面有 Cloudflare：边缘会缓存 /static 下的图，并把浏览器缓存改写成数小时，
 * 源站 no-cache 管不到。换图后要么去 Cloudflare 清这几个 URL，要么把下面的版本号改掉随部署上线。
 */
const FLOOR_IMG_VERSION = "20261010";
const floorImg = (name: string) => `/static/floors/${name}.webp?v=${FLOOR_IMG_VERSION}`;

const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    bgImage: floorImg("safety"),
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    bgImage: floorImg("decoration"),
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    bgImage: floorImg("doors"),
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    bgImage: floorImg("electrical"),
  },
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    bgImage: floorImg("tools"),
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    bgImage: floorImg("fasteners"),
  },
];

const FLOOR_ITEMS: FloorItem[] = FLOOR_CONFIGS.map((c) => ({
  id: c.id,
  nameKey: c.nameKey,
}));

export function CategoryFloors() {
  const { data, isLoading } = useSWR(
    "home-floor-products",
    listHomeFloorProducts,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    },
  );

  return (
    <div id="category-floors-container">
      <FloorElevator floors={FLOOR_ITEMS} />
      <div className="space-y-5">
        {FLOOR_CONFIGS.map((config) => (
          <CategoryFloorSection
            key={config.id}
            config={config}
            products={data?.floors[config.id]?.products}
            categories={data?.floors[config.id]?.categories}
            isLoading={isLoading}
          />
        ))}
      </div>
    </div>
  );
}
