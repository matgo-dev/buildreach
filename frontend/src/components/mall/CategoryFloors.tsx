"use client";

import useSWR from "swr";

import { listHomeFloorProducts } from "@/lib/api/products";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * 楼层品类映射由后端按 name_zh 路径解析，前端只负责展示。
 * 展示版与 matgo 共用后端(uploads 卷里是 matgo 的绿色楼层图),
 * 所以 bgImage 走前端自带的 public/images/floors/*.webp(炭黑+明黄色系),换图随部署上线。
 */
const floorImg = (name: string) => `/images/floors/${name}.webp`;

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
