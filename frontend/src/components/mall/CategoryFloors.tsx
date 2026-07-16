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
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    bgImage: "/static/floors/safety.webp",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    bgImage: "/static/floors/decoration.webp",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    bgImage: "/static/floors/doors.webp",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    bgImage: "/static/floors/electrical.webp",
  },
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    bgImage: "/static/floors/tools.webp",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    bgImage: "/static/floors/fasteners.webp",
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
