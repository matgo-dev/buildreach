"use client";

import useSWR from "swr";

import { listHomeFloorProducts } from "@/lib/api/products";
import { CategoryFloorSection, type FloorConfig } from "./CategoryFloorSection";
import { FloorElevator, type FloorItem } from "./FloorElevator";

/**
 * 6 个品类楼层的配置。
 * 楼层品类映射由后端按 name_zh 路径解析，前端只负责展示。
 * 左区背景图由 /home-floors 每层给出 bg_image(/static/floors/*.webp?v=<内容指纹>,图片存 uploads/floors 卷,
 * 换图替换文件即可,免部署;URL 随内容变,Cloudflare/浏览器缓存自然失效)。
 * 接口未返回前不铺背景(只有底色),避免先请求一个不带版本号的 URL 再换成带指纹的,首屏图闪两次。
 */
const FLOOR_CONFIGS: FloorConfig[] = [
  {
    id: "floor-safety",
    nameKey: "floorSafetyProtection",
  },
  {
    id: "floor-decoration",
    nameKey: "floorDecorationBuilding",
  },
  {
    id: "floor-doors",
    nameKey: "floorDoorsWindowsHardware",
  },
  {
    id: "floor-electrical",
    nameKey: "floorIndustrialElectrical",
  },
  {
    id: "floor-tools",
    nameKey: "floorToolsConsumables",
  },
  {
    id: "floor-fasteners",
    nameKey: "floorFastenersSealing",
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
            config={{ ...config, bgImage: data?.floors[config.id]?.bg_image }}
            products={data?.floors[config.id]?.products}
            categories={data?.floors[config.id]?.categories}
            isLoading={isLoading}
          />
        ))}
      </div>
    </div>
  );
}
