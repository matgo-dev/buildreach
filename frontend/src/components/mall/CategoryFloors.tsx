"use client";

import { useCategoryTree } from "@/hooks/useCategoryTree";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * categoryCodes 对应 DB 中多个 L1 品类 code，楼层合并展示其下 L2 子品类。
 * 参考鑫方盛首页楼层映射（4 个重合楼层已确认，门窗五金/装饰建材为自定义待确认）。
 * bgImage 使用用户提供的品类展示图（鑫方盛风格，竖长图底部有产品实物）。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
    categoryCodes: ["02"],              // 手动工具（参考鑫方盛）
    bgImage: "/images/floors/tools.png",
  },
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
    categoryCodes: ["01", "04", "22"],   // 劳保 + 安防 + 临建(道路安全)（参考鑫方盛）
    bgImage: "/images/floors/safety.png",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
    categoryCodes: ["03"],              // 紧固件（参考鑫方盛）
    bgImage: "/images/floors/fasteners.png",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
    categoryCodes: ["10", "11", "14", "15", "31"], // 电器+灯具+工控+电工+配电（参考鑫方盛）
    bgImage: "/images/floors/electrical.png",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
    categoryCodes: ["20", "25", "27"],  // 门窗+水暖+卫浴（待领导确认）
    bgImage: "/images/floors/doors.png",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
    categoryCodes: ["17", "18", "19"],  // 防水+涂料+装饰材料（待领导确认）
    bgImage: "/images/floors/decoration.png",
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
