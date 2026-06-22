"use client";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * categoryCode 对应 DB 中 L1 品类 code，暂无数据时楼层显示占位。
 * bgImage 使用用户提供的品类展示图（鑫方盛风格，竖长图底部有产品实物）。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    categoryCode: "01",
    bgImage: "/images/floors/tools.png",
  },
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    categoryCode: "02",
    bgImage: "/images/floors/safety.png",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    categoryCode: "03",
    bgImage: "/images/floors/fasteners.png",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    categoryCode: "04",
    bgImage: "/images/floors/electrical.png",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    categoryCode: "05",
    bgImage: "/images/floors/decoration.png", // 暂用装饰建材图，待替换
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    categoryCode: "06",
    bgImage: "/images/floors/electrical.png", // 暂复用工控配电图，待替换
  },
];

const FLOOR_ITEMS: FloorItem[] = FLOOR_CONFIGS.map((c) => ({
  id: c.id,
  nameKey: c.nameKey,
}));

export function CategoryFloors() {
  const { tree: categoryTree } = useCategoryTree();

  return (
    <div id="category-floors-container">
      <FloorElevator floors={FLOOR_ITEMS} />
      <div className="space-y-5">
        {FLOOR_CONFIGS.map((config) => (
          <CategoryFloorSection
            key={config.id}
            config={config}
            categoryTree={categoryTree}
          />
        ))}
      </div>
    </div>
  );
}
