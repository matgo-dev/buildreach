// 买方公开商品 API client
//
// 后端契约: backend/app/api/v1/products.py
// 断层隔离: 不含任何供应商字段

import { api } from "../api";

// ---------- 列表 ----------

export interface ProductPublic {
  id: number;
  spu_code: string;
  name: string;
  description: string | null;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  certifications: string[] | null;
  is_featured: boolean;
  supply_mode: string;
  main_image: string | null;
  main_image_thumbnail: string | null;
  unit: string | null;
  moq: number | null;
  moq_unit: string | null;
  // 兼容字段:买方 API 已不返回,RFQ 模块仍引用
  price_min?: number | null;
  price_max?: number | null;
  currency?: string | null;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  sku_count?: number;
  /** SPU 英文名,专区列表返回作卡片副标;mall 不返回 */
  name_en?: string | null;
}

export interface ProductListParams {
  category_code?: string;
  keyword?: string;
  featured?: boolean;
  supply_mode?: string;
  certification?: string;
  brand?: string;
  sort?: "newest";
  page?: number;
  size?: number;
  all_categories?: boolean;
}

export interface ProductListResponse {
  items: ProductPublic[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface HomeFloorCategory {
  code: string;
  name: string;
  name_zh: string;
  level: number;
}

export interface HomeFloorData {
  categories: HomeFloorCategory[];
  products: ProductPublic[];
}

export interface HomeFloorProductsResponse {
  floors: Record<string, HomeFloorData>;
  generated_at: string;
  ttl_seconds: number;
}

// ---------- 详情 ----------

export interface ProductImage {
  id: number;
  image_key: string;
  full_url: string;
  thumbnail_url: string;
  image_type: string;
  sort_order: number;
  sku_id: number | null;
  width: number | null;
  height: number | null;
  file_size: number | null;
}

/** 属性值 — 支持文本和色板图片 */
export interface AttrValue {
  value: string;
  value_type: string;
  swatch_image: string | null;
}

/** 属性项 — 同 key 多值聚合 */
export interface AttrItem {
  key: string;
  unit: string | null;
  values: AttrValue[];
  /** 后端标记:true=可选规格轴(颜色/厚度),false=纯展示(特性等) */
  selectable: boolean;
}

/** 属性分组 — 按 attr_group 归类 */
export interface AttrGroup {
  group: string;
  items: AttrItem[];
}

export interface ProductPublicDetail {
  id: number;
  spu_code: string;
  name: string;
  description: string | null;
  detail_description: string | null;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  manufacturer_model: string | null;
  hs_code: string | null;
  certifications: string[] | null;
  selling_points: string | null;
  moq: number | null;
  moq_unit: string | null;
  is_featured: boolean;
  supply_mode: string;
  unit: string;
  attribute_groups: AttrGroup[];
  images: ProductImage[];
  // 兼容字段:买方 API 已不返回,RFQ 模块仍引用(后续迁移到运营 API)
  skus?: SkuPublic[];
  attributes?: ProductAttr[];
  currency?: string;
  price_min?: number | null;
  price_max?: number | null;
}

// ---------- 兼容类型(RFQ 等模块仍引用,后续随 SKU 维度定调后清理) ----------

export interface PriceTier {
  id: number;
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
  currency: string;
  label: string | null;
}

export interface ProductAttr {
  attr_key: string;
  attr_value: string;
  attr_unit: string | null;
  sort_order: number;
  sku_id: number | null;
  display_name: string | null;
}

export interface SkuPublic {
  id: number;
  sku_code: string;
  name: string | null;
  color: string | null;
  material: string | null;
  manufacturer_model: string | null;
  price_min: number | null;
  price_max: number | null;
  moq: number;
  lead_time_min: number | null;
  lead_time_max: number | null;
  is_default: boolean;
  status: string;
  price_tiers: PriceTier[];
  images: ProductImage[];
  attributes: ProductAttr[];
}

// ---------- API 函数 ----------

export async function listProducts(
  params: ProductListParams = {}
): Promise<ProductListResponse> {
  const qs = new URLSearchParams();
  if (params.category_code) qs.set("category_code", params.category_code);
  if (params.keyword) qs.set("keyword", params.keyword);
  if (params.featured !== undefined) qs.set("featured", String(params.featured));
  if (params.supply_mode) qs.set("supply_mode", params.supply_mode);
  if (params.certification) qs.set("certification", params.certification);
  if (params.brand) qs.set("brand", params.brand);
  if (params.sort) qs.set("sort", params.sort);
  if (params.page) qs.set("page", String(params.page));
  if (params.size) qs.set("size", String(params.size));
  if (params.all_categories) qs.set("all_categories", "true");
  const q = qs.toString();
  return api.get<ProductListResponse>(`/api/v1/products${q ? `?${q}` : ""}`);
}

export async function listHomeFloorProducts(): Promise<HomeFloorProductsResponse> {
  return api.get<HomeFloorProductsResponse>("/api/v1/products/home-floors");
}

export async function listCertificationOptions(): Promise<string[]> {
  return api.get<string[]>("/api/v1/products/certification-options");
}

export async function listBrands(categoryCode?: string): Promise<string[]> {
  const qs = categoryCode ? `?category_code=${categoryCode}` : "";
  return api.get<string[]>(`/api/v1/products/brands${qs}`);
}

export async function getProduct(id: number): Promise<ProductPublicDetail> {
  return api.get<ProductPublicDetail>(`/api/v1/products/${id}`);
}
