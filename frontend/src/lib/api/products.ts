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
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  certifications: string[] | null;
  is_featured: boolean;
  main_image: string | null;
  price_min: number | null;
  price_max: number | null;
  currency: string | null;
  moq: number | null;
  unit: string | null;
  lead_time_min: number | null;
  lead_time_max: number | null;
  sku_count: number;
}

export interface ProductListParams {
  category_code?: string;
  keyword?: string;
  featured?: boolean;
  sort?: "newest" | "price_asc" | "price_desc";
  page?: number;
  size?: number;
}

export interface ProductListResponse {
  items: ProductPublic[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ---------- 详情 ----------

export interface PriceTier {
  id: number;
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
  currency: string;
  label: string | null;
}

export interface ProductImage {
  id: number;
  image_key: string;
  full_url: string;
  image_type: string;
  sort_order: number;
  sku_id: number | null;
  width: number | null;
  height: number | null;
  file_size: number | null;
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
  currency: string;
  unit: string;
  moq: number;
  lead_time_min: number | null;
  lead_time_max: number | null;
  is_default: boolean;
  status: string;
  price_tiers: PriceTier[];
  images: ProductImage[];
  attributes: ProductAttr[];
}

export interface ProductPublicDetail {
  id: number;
  spu_code: string;
  name: string;
  description: string | null;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  hs_code: string | null;
  certifications: string[] | null;
  selling_points: string | null;
  is_featured: boolean;
  price_min: number | null;
  price_max: number | null;
  skus: SkuPublic[];
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
  if (params.sort) qs.set("sort", params.sort);
  if (params.page) qs.set("page", String(params.page));
  if (params.size) qs.set("size", String(params.size));
  const q = qs.toString();
  return api.get<ProductListResponse>(`/api/v1/products${q ? `?${q}` : ""}`);
}

export async function getProduct(id: number): Promise<ProductPublicDetail> {
  return api.get<ProductPublicDetail>(`/api/v1/products/${id}`);
}
