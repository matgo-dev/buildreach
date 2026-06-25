"use client";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * categoryCodes 对应 DB 中多个 L1 品类 code，楼层合并展示其下 L2 子品类。
 * bgImage 使用用户提供的品类展示图（鑫方盛风格，竖长图底部有产品实物）。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    categoryCodes: ["21", "22"],         // 劳保(21) + 安防(22)
    bgImage: "/images/floors/safety.png",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    categoryCodes: ["28"],              // 紧固件（XFS code=28）
    bgImage: "/images/floors/fasteners.png",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    categoryCodes: ["30", "16", "33", "34", "49"], // 电器(30)+灯具(16)+工控(33)+电工(34)+配电(49)
    bgImage: "/images/floors/electrical.png",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    categoryCodes: ["38", "43", "45"],  // 门窗(38)+水暖(43)+卫浴(45)
    bgImage: "/images/floors/doors.png",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    categoryCodes: ["36", "37", "09"],  // 防水(36)+涂料(37)+装饰材料(09)
    bgImage: "/images/floors/decoration.png",
  },
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    categoryCodes: ["24"],              // 手动工具（XFS code=24）
    bgImage: "/images/floors/tools.png",
    excludeSubcategoryCodes: ["24.017", "24.020"], // 排除园林工具、土杂工具
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
