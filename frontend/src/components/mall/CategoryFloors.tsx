"use client";

import useSWR from "swr";

import { listHomeFloorProducts } from "@/lib/api/products";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * 楼层品类映射由后端按 name_zh 路径解析，前端只负责展示。
 * bgImage 使用用户提供的品类展示图（鑫方盛风格，竖长图底部有产品实物）。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    bgImage: "/images/floors/safety.webp",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    bgImage: "/images/floors/decoration.webp",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    bgImage: "/images/floors/doors.webp",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    bgImage: "/images/floors/electrical.webp",
  },
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    bgImage: "/images/floors/tools.webp",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    bgImage: "/images/floors/fasteners.webp",
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
