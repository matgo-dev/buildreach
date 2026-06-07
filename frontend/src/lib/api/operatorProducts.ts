// /api/v1/operator/products 客户端
//
// 后端契约见 backend/app/api/v1/operator_products.py
// Schema 见 backend/app/schemas/product.py

import { api, apiRequest } from "../api";
import { useAuthStore } from "@/stores/authStore";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
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
  currency?: string;
  unit: SkuUnitCode;
  moq: number;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate?: boolean;
  cargo_type?: string | null;
  is_default?: boolean;
  status?: string;
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
  status?: string;
  attributes?: ProductAttrInput[] | null;
}

export interface ProductCreatedResponse {
  id: number;
  spu_code: string;
}

export interface ProductStatusInput {
  status: string;  // DRAFT / ACTIVE / INACTIVE
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
  main_image: string | null;
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

// ---------- API 函数 ----------

export const operatorProductsApi = {
  /** 商品列表(分页 + 筛选) */
  list: (params?: ProductListParams) => {
    const qs = new URLSearchParams();
    if (params?.category_code) qs.set("category_code", params.category_code);
    if (params?.status) qs.set("status", params.status);
    if (params?.keyword) qs.set("keyword", params.keyword);
    if (params?.page !== undefined) qs.set("page", String(params.page));
    if (params?.size !== undefined) qs.set("size", String(params.size));
    const q = qs.toString();
    return api.get<ProductPage>(`${PREFIX}${q ? `?${q}` : ""}`);
  },

  /** 商品详情 */
  detail: (id: number) =>
    api.get(`${PREFIX}/${id}`),

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
    const url = `${BASE_URL}${PREFIX}/${productId}/images${qs}`;

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

  /** 改状态（上架/下架） */
  updateStatus: (productId: number, data: ProductStatusInput) =>
    api.patch<{ id: number; status: string }>(`${PREFIX}/${productId}/status`, data),
};
