/**
 * SKU 颜色 / 材质预置选项 key。
 * 显示文本走 i18n（skuOptions namespace），运营可选可输。
 * 存入数据库的是用户看到的文本（非 key），方便买家端直接展示。
 */

export const COLOR_KEYS = [
  "white",
  "black",
  "gray",
  "silver",
  "red",
  "blue",
  "green",
  "yellow",
  "orange",
  "brown",
  "transparent",
  "natural",
] as const;

export const MATERIAL_KEYS = [
  "carbon_steel",
  "stainless_steel",
  "galvanized_steel",
  "aluminum",
  "copper",
  "pvc",
  "ppr",
  "pe",
  "abs",
  "glass",
  "wood",
  "rubber",
  "ceramic",
  "concrete",
  "fiber",
] as const;
