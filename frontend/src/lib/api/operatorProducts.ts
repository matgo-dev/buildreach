// /api/v1/operator/products 客户端
//
// 后端契约见 backend/app/api/v1/operator_products.py
// Schema 见 backend/app/schemas/product.py

import { api, apiRequest } from "../api";
import { useAuthStore } from "@/stores/authStore";
import { getApiBase } from "@/lib/env";
const PREFIX = "/api/v1/operator/products";

// ---------- 枚举 ----------

export const SKU_UNITS = [
  "PCS", "SET", "PAIR", "M", "M2", "M3", "KG", "TON",
  "ROLL", "SHEET", "BOX", "BAG", "BARREL", "L", "BUNDLE",
] as const;

export type SkuUnitCode = (typeof SKU_UNITS)[number];

// ---------- 属性模板 ----------

export interface AttrTemplate {
  id: number;
  category_code: string;
  attr_key: string;
  display_name: string;
  attr_type: string;          // text / number / select
  attr_unit: string | null;
  options: Record<string, unknown> | unknown[] | null;
  is_required: boolean;
  sort_order: number;
  scope: "SPU" | "SKU";
  selectable: boolean;
}

// ---------- 属性(提交用) ----------

export interface ProductAttrInput {
  attr_key: string;
  attr_value: string;
}

// ---------- 阶梯价 ----------

export interface PriceTierInput {
  min_qty: number;
  max_qty: number | null;
  unit_price: number;         // 后端 Decimal，前端用 number
  currency: string;
  label?: string | null;
}

export interface PriceTierSchema {
  id: number;
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
  currency: string;
  label: string | null;
}

// ---------- 图片 ----------

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

// ---------- SKU ----------

export interface SkuCreateInput {
  sku_code?: string | null;
  manufacturer_model?: string | null;
  name?: string | null;
  color?: string | null;
  material?: string | null;
  source_lang?: string;
  price_min?: number | null;
  price_max?: number | null;
  moq: number;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean;
  cargo_type?: string | null;
  is_default?: boolean;
  price_tiers?: PriceTierInput[] | null;
  attributes?: ProductAttrInput[] | null;
}

export interface SkuCreatedResponse {
  id: number;
  sku_code: string;
}

// ---------- SPU ----------

export interface ProductCreateInput {
  category_code: string;
  spu_code?: string | null;
  name: string;
  description?: string | null;
  origin?: string;
  hs_code?: string | null;
  brand?: string | null;
  certifications?: unknown[] | null;
  selling_points?: string | null;
  source_lang?: string;
  is_featured?: boolean;
  supply_mode?: string;
  unit?: SkuUnitCode;
  currency?: string;
  // 物流参数（SPU 级）
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean;
  cargo_type?: string | null;
  attributes?: ProductAttrInput[] | null;
}

export interface ProductCreatedResponse {
  id: number;
  spu_code: string;
  skus?: { client_id: string | null; id: number; sku_code: string }[];
}

export interface ProductStatusInput {
  status: string;  // DRAFT / ACTIVE / INACTIVE
}

// ---------- 供应商关系(详情用) ----------

export interface SupplierRelationDetail {
  id: number;
  sku_id: number;
  supplier_org_id: number;
  supplier_org_name: string;
  supplier_price: number;
  supplier_currency: string;
  cif_price_usd: number | null;
  supplier_moq: number | null;
  supplier_lead_time_days: number | null;
  pvoc_status: string | null;
  has_coc: boolean;
  is_preferred: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------- 属性详情 ----------

export interface ProductAttrDetail {
  attr_key: string;
  attr_value: string;
  attr_unit: string | null;
  sort_order: number;
  sku_id: number | null;
  display_name: string | null;
}

// ---------- SKU 详情(运营端) ----------

export interface SkuOperatorDetail {
  id: number;
  sku_code: string;
  name: string | null;
  name_zh: string | null;
  name_en: string | null;
  color: string | null;
  color_zh: string | null;
  color_en: string | null;
  material: string | null;
  material_zh: string | null;
  material_en: string | null;
  manufacturer_model: string | null;
  source_lang: string;
  price_min: number | null;
  price_max: number | null;
  moq: number;
  lead_time_min: number | null;
  lead_time_max: number | null;
  packing_quantity: number | null;
  gross_weight_kg: number | null;
  volume_cbm: number | null;
  can_consolidate: boolean;
  cargo_type: string | null;
  is_default: boolean;
  status: string;
  price_tiers: PriceTierSchema[];
  images: ProductImage[];
  attributes: ProductAttrDetail[];
  supplier_relations: SupplierRelationDetail[];
  created_at: string;
  updated_at: string;
}

// ---------- 商品详情(运营端) ----------

export interface ProductOperatorDetail {
  id: number;
  spu_code: string;
  name: string;
  name_zh: string | null;
  name_en: string | null;
  description: string | null;
  description_zh: string | null;
  description_en: string | null;
  category_code: string;
  category_name: string;
  origin: string;
  origin_zh: string | null;
  origin_en: string | null;
  brand: string | null;
  brand_zh: string | null;
  brand_en: string | null;
  hs_code: string | null;
  certifications: string[] | null;
  selling_points: string | null;
  selling_points_zh: string | null;
  selling_points_en: string | null;
  source_lang: string;
  is_featured: boolean;
  supply_mode: string;
  unit: string;
  currency: string;
  moq: number | null;
  moq_unit: string | null;
  ref_price_tiers: unknown[] | null;
  // 物流参数（SPU 级）
  lead_time_min: number | null;
  lead_time_max: number | null;
  packing_quantity: number | null;
  gross_weight_kg: number | null;
  volume_cbm: number | null;
  can_consolidate: boolean;
  cargo_type: string | null;
  status: string;
  created_by_name: string;
  skus: SkuOperatorDetail[];
  images: ProductImage[];
  attributes: ProductAttrDetail[];
  created_at: string;
  updated_at: string;
}

// ---------- SPU 更新入参 ----------

export interface ProductUpdateInput {
  name?: string | null;
  description?: string | null;
  origin?: string | null;
  hs_code?: string | null;
  brand?: string | null;
  certifications?: string[] | null;
  selling_points?: string | null;
  is_featured?: boolean | null;
  supply_mode?: string | null;
  // 物流参数（SPU 级）
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean | null;
  cargo_type?: string | null;
  attributes?: ProductAttrInput[] | null;
}

// ---------- SKU 更新入参 ----------

export interface SkuUpdateInput {
  manufacturer_model?: string | null;
  name?: string | null;
  color?: string | null;
  material?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  moq?: number | null;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean | null;
  cargo_type?: string | null;
  is_default?: boolean | null;
  price_tiers?: PriceTierInput[] | null;
  attributes?: ProductAttrInput[] | null;
}

// ---------- 列表项(对齐 ProductOperator schema) ----------

export interface ProductOperatorItem {
  id: number;
  spu_code: string;
  name: string;
  name_zh: string | null;
  name_en: string | null;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  is_featured: boolean;
  supply_mode: string;
  main_image: string | null;
  main_image_thumbnail: string | null;
  status: string;
  created_by_name: string;
  price_min: number | null;
  price_max: number | null;
  currency: string | null;
  sku_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductListParams {
  category_code?: string;
  status?: string;
  supply_mode?: string;
  keyword?: string;
  page?: number;
  size?: number;
}

export interface ProductPage {
  items: ProductOperatorItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ---------- 聚合保存 ----------

export interface ImageRefInput {
  image_id: number;
  image_type: "MAIN" | "GALLERY" | "DETAIL";
  sort_order: number;
}

export interface AggregateSkuInput {
  id?: number | null;
  client_id?: string | null;
  manufacturer_model?: string | null;
  name?: string | null;
  color?: string | null;
  material?: string | null;
  source_lang?: string;
  price_min?: number | null;
  price_max?: number | null;
  moq: number;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean;
  cargo_type?: string | null;
  is_default?: boolean;
  price_tiers?: PriceTierInput[] | null;
  attributes?: ProductAttrInput[] | null;
}

export interface ProductAggregateCreateInput {
  category_code: string;
  spu_code?: string | null;
  name: string;
  description?: string | null;
  origin?: string;
  hs_code?: string | null;
  brand?: string | null;
  certifications?: unknown[] | null;
  selling_points?: string | null;
  source_lang?: string;
  is_featured?: boolean;
  supply_mode?: string;
  unit?: SkuUnitCode;
  currency?: string;
  // 物流参数（SPU 级）
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean;
  cargo_type?: string | null;
  attributes?: ProductAttrInput[] | null;
  skus: AggregateSkuInput[];
  images?: ImageRefInput[] | null;
}

export interface ProductAggregateSaveInput {
  name?: string | null;
  description?: string | null;
  origin?: string | null;
  hs_code?: string | null;
  brand?: string | null;
  certifications?: string[] | null;
  selling_points?: string | null;
  is_featured?: boolean | null;
  supply_mode?: string | null;
  unit?: SkuUnitCode | null;
  currency?: string | null;
  // 物流参数（SPU 级）
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean | null;
  cargo_type?: string | null;
  attributes?: ProductAttrInput[] | null;
  skus?: AggregateSkuInput[] | null;
  images?: ImageRefInput[] | null;
}

// ---------- API 函数 ----------

export const operatorProductsApi = {
  /** 商品列表(分页 + 筛选) */
  list: (params?: ProductListParams) => {
    const qs = new URLSearchParams();
    if (params?.category_code) qs.set("category_code", params.category_code);
    if (params?.status) qs.set("status", params.status);
    if (params?.supply_mode) qs.set("supply_mode", params.supply_mode);
    if (params?.keyword) qs.set("keyword", params.keyword);
    if (params?.page !== undefined) qs.set("page", String(params.page));
    if (params?.size !== undefined) qs.set("size", String(params.size));
    const q = qs.toString();
    return api.get<ProductPage>(`${PREFIX}${q ? `?${q}` : ""}`);
  },

  /** 商品详情 */
  detail: (id: number) =>
    api.get<ProductOperatorDetail>(`${PREFIX}/${id}`),

  /** 更新商品(SPU) */
  update: (id: number, data: ProductUpdateInput) =>
    api.put<{ id: number }>(`${PREFIX}/${id}`, data),

  /** 更新 SKU */
  updateSku: (productId: number, skuId: number, data: SkuUpdateInput) =>
    api.put<{ id: number; sku_code: string }>(`${PREFIX}/${productId}/skus/${skuId}`, data),

  /** 删除 SKU */
  deleteSku: (productId: number, skuId: number) =>
    api.delete(`${PREFIX}/${productId}/skus/${skuId}`),

  /** 删除草稿商品 */
  remove: (id: number) =>
    api.delete(`${PREFIX}/${id}`),

  /** 品类属性模板（传 L3 叶子 code，后端按祖先链合并返回） */
  getAttrTemplates: (categoryCode: string) =>
    api.get<AttrTemplate[]>(`${PREFIX}/attr-templates/${categoryCode}`),

  /** 创建商品(SPU) */
  create: (data: ProductCreateInput) =>
    api.post<ProductCreatedResponse>(PREFIX, data),

  /** 创建 SKU */
  createSku: (productId: number, data: SkuCreateInput) =>
    api.post<SkuCreatedResponse>(`${PREFIX}/${productId}/skus`, data),

  /** 上传图片（multipart/form-data）；SKU 图带 sku_id */
  uploadImage: async (productId: number, file: File, skuId?: number): Promise<ProductImage> => {
    const qs = skuId != null ? `?sku_id=${skuId}` : "";
    const url = `${getApiBase()}${PREFIX}/${productId}/images${qs}`;

    const formData = new FormData();
    formData.append("file", file);

    const token = useAuthStore.getState().accessToken;
    const lang = typeof document !== "undefined" ? document.documentElement.lang || "zh" : "zh";

    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "Accept-Language": lang,
      },
      body: formData,
    });

    const json = await res.json();
    if (!res.ok || json.code !== 0) {
      throw new Error(json.message ?? "Image upload failed");
    }
    return json.data as ProductImage;
  },

  /** 删除图片 */
  deleteImage: (productId: number, imageId: number) =>
    api.delete(`${PREFIX}/${productId}/images/${imageId}`),

  /** 设为主图 */
  setMainImage: (productId: number, imageId: number) =>
    api.patch(`${PREFIX}/${productId}/images/${imageId}/set-main`),

  /** 图片排序 */
  sortImages: (productId: number, imageIds: number[]) =>
    api.patch(`${PREFIX}/${productId}/images/sort`, imageIds),

  /** 改状态（上架/下架）；force=true 跳过上架校验 */
  updateStatus: (productId: number, data: ProductStatusInput, force?: boolean) =>
    api.patch<{ id: number; status: string }>(
      `${PREFIX}/${productId}/status${force ? "?force=true" : ""}`, data,
    ),

  /** 改 SKU 状态（启用/停用） */
  updateSkuStatus: (productId: number, skuId: number, data: { status: "ACTIVE" | "INACTIVE" }) =>
    api.patch<{ id: number; status: string }>(
      `${PREFIX}/${productId}/skus/${skuId}/status`, data,
    ),

  /** 聚合创建（SPU+SKU 单事务） */
  createAggregate: (data: ProductAggregateCreateInput) =>
    api.post<ProductCreatedResponse>(`${PREFIX}/aggregate`, data),

  /** 聚合保存（SPU+SKU diff 单事务） */
  saveAggregate: (productId: number, data: ProductAggregateSaveInput) =>
    api.put<{ id: number }>(`${PREFIX}/${productId}/aggregate`, data),
};
