"use client";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * categoryCode 对应 DB 中 L1 品类 code，暂无数据时楼层显示占位。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    categoryCode: "01",
    gradient: "linear-gradient(135deg, #0D4D4D 0%, #1A6B6B 100%)",
    bgImage: "/images/floors/tools.svg",
  },
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    categoryCode: "02",
    gradient: "linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%)",
    bgImage: "/images/floors/safety.svg",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    categoryCode: "03",
    gradient: "linear-gradient(135deg, #37474F 0%, #546E7A 100%)",
    bgImage: "/images/floors/fasteners.svg",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    categoryCode: "04",
    gradient: "linear-gradient(135deg, #1565C0 0%, #1976D2 100%)",
    bgImage: "/images/floors/electrical.svg",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    categoryCode: "05",
    gradient: "linear-gradient(135deg, #4E342E 0%, #6D4C41 100%)",
    bgImage: "/images/floors/doors.svg",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    categoryCode: "06",
    gradient: "linear-gradient(135deg, #BF360C 0%, #E65100 100%)",
    bgImage: "/images/floors/decoration.svg",
  },
];

const FLOOR_ITEMS: FloorItem[] = FLOOR_CONFIGS.map((c) => ({
  id: c.id,
  nameKey: c.nameKey,
}));

/**
 * 品类楼层区域 — 包含左侧电梯导航 + 6 个品类楼层。
 * 放在首页 HeroBanner 下方、平台能力区上方。
 */
export function CategoryFloors() {
  const { tree: categoryTree } = useCategoryTree();

  return (
    <div id="category-floors-container" className="flex gap-4 items-start">
      {/* 左侧楼层电梯 — sticky 占位式 */}
      <FloorElevator floors={FLOOR_ITEMS} />

      {/* 楼层列表 */}
      <div className="flex-1 min-w-0 space-y-5">
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
