/**
 * 商品模块 API 封装 — SPU + SKU 两层化。
 *
 * 类型与后端 schemas/product.py 对齐。
 */
import { api } from "./api";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// ── 阶梯价 ──────────────────────────────────────────────

export interface SkuPriceTier {
  id: number;
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
  currency: string;
  label: string | null;
}

export interface SkuPriceTierCreate {
  min_qty: number;
  max_qty: number | null;
  unit_price: number;
  currency?: string;
  label?: string | null;
}

// ── 图片 ────────────────────────────────────────────────

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

// ── 品类属性 ────────────────────────────────────────────

export interface ProductAttr {
  attr_key: string;
  attr_value: string;
  attr_unit: string | null;
  sort_order: number;
}

// ── 供货关系（挂 SKU）────────────────────────────────────

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

// ── SKU ─────────────────────────────────────────────────

/** 买方 SKU 响应（不含供应商） */
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
  price_tiers: SkuPriceTier[];
  images: ProductImage[];
}

/** 运营 SKU 响应（含供应商 + 物流参数） */
export interface SkuOperator extends SkuPublic {
  name_i18n: Record<string, string> | null;
  color_i18n: Record<string, string> | null;
  material_i18n: Record<string, string> | null;
  packing_quantity: number | null;
  gross_weight_kg: number | null;
  volume_cbm: number | null;
  can_consolidate: boolean;
  cargo_type: string | null;
  supplier_relations: SupplierRelationDetail[];
  created_at: string;
  updated_at: string;
}

// ── 商品(SPU) — 公开（买方） ────────────────────────────

export interface ProductPublic {
  id: number;
  spu_code: string;
  name: string;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  certifications: string[];
  is_featured: boolean;
  main_image: string | null;
  /** 默认 SKU 展示价 */
  price_min: number | null;
  price_max: number | null;
  currency: string | null;
  sku_count: number;
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
  certifications: string[];
  selling_points: string | null;
  is_featured: boolean;
  skus: SkuPublic[];
  images: ProductImage[];
  attributes: ProductAttr[];
}

// ── 商品(SPU) — 运营 ───────────────────────────────────

export interface ProductOperator {
  id: number;
  spu_code: string;
  name: string;
  name_i18n: Record<string, string> | null;
  category_code: string;
  category_name: string;
  origin: string;
  brand: string | null;
  is_featured: boolean;
  main_image: string | null;
  status: string;
  created_by_name: string;
  /** 默认 SKU 展示价 */
  price_min: number | null;
  price_max: number | null;
  currency: string | null;
  sku_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductOperatorDetail {
  id: number;
  spu_code: string;
  name: string;
  name_i18n: Record<string, string> | null;
  description: string | null;
  description_i18n: Record<string, string> | null;
  category_code: string;
  category_name: string;
  origin: string;
  origin_i18n: Record<string, string> | null;
  brand: string | null;
  brand_i18n: Record<string, string> | null;
  hs_code: string | null;
  certifications: string[];
  selling_points: string | null;
  selling_points_i18n: Record<string, string> | null;
  is_featured: boolean;
  status: string;
  created_by_name: string;
  skus: SkuOperator[];
  images: ProductImage[];
  attributes: ProductAttr[];
  created_at: string;
  updated_at: string;
}

// ── 属性模板 ────────────────────────────────────────────

export interface AttrTemplate {
  id: number;
  category_code: string;
  attr_key: string;
  display_name: string;
  attr_type: string;
  attr_unit: string | null;
  options: string[] | null;
  is_required: boolean;
  sort_order: number;
}

// ── 分页 ────────────────────────────────────────────────

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── 工具 ────────────────────────────────────────────────

function toQueryString(
  params: Record<string, string | number | boolean | undefined>,
): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  });
  return qs.toString();
}

// ── 公开接口 ────────────────────────────────────────────

export const publicProductApi = {
  list: (params: Record<string, string | number | boolean | undefined>) =>
    api.get<PageResult<ProductPublic>>(`/api/v1/products?${toQueryString(params)}`),

  detail: (id: number) =>
    api.get<ProductPublicDetail>(`/api/v1/products/${id}`),
};

// ── 运营接口 ────────────────────────────────────────────

export const operatorProductApi = {
  // SPU CRUD
  list: (params: Record<string, string | number | boolean | undefined>) =>
    api.get<PageResult<ProductOperator>>(
      `/api/v1/operator/products?${toQueryString(params)}`,
    ),

  detail: (id: number) =>
    api.get<ProductOperatorDetail>(`/api/v1/operator/products/${id}`),

  create: (data: Record<string, unknown>) =>
    api.post<{ id: number; spu_code: string }>(
      "/api/v1/operator/products",
      data,
    ),

  update: (id: number, data: Record<string, unknown>) =>
    api.put<{ id: number }>(`/api/v1/operator/products/${id}`, data),

  updateStatus: (id: number, status: string) =>
    api.patch<{ id: number; status: string }>(
      `/api/v1/operator/products/${id}/status`,
      { status },
    ),

  delete: (id: number) => api.delete(`/api/v1/operator/products/${id}`),

  // SKU CRUD
  skus: {
    list: (productId: number) =>
      api.get<SkuOperator[]>(
        `/api/v1/operator/products/${productId}/skus`,
      ),

    create: (productId: number, data: Record<string, unknown>) =>
      api.post<{ id: number; sku_code: string }>(
        `/api/v1/operator/products/${productId}/skus`,
        data,
      ),

    update: (
      productId: number,
      skuId: number,
      data: Record<string, unknown>,
    ) =>
      api.put<{ id: number }>(
        `/api/v1/operator/products/${productId}/skus/${skuId}`,
        data,
      ),

    delete: (productId: number, skuId: number) =>
      api.delete(
        `/api/v1/operator/products/${productId}/skus/${skuId}`,
      ),
  },

  // 图片（支持 sku_id 维度）
  uploadImage: async (
    productId: number,
    file: File,
    skuId?: number,
  ): Promise<ProductImage> => {
    const { useAuthStore } = await import("@/stores/authStore");
    const token = useAuthStore.getState().accessToken;
    const formData = new FormData();
    formData.append("file", file);
    const skuParam = skuId != null ? `?sku_id=${skuId}` : "";
    const res = await fetch(
      `${BASE}/api/v1/operator/products/${productId}/images${skuParam}`,
      {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      },
    );
    const json = await res.json();
    if (!res.ok || json.code !== 0)
      throw new Error(json.message || "Upload failed");
    return json.data;
  },

  deleteImage: (productId: number, imageId: number) =>
    api.delete(
      `/api/v1/operator/products/${productId}/images/${imageId}`,
    ),

  setMainImage: (productId: number, imageId: number) =>
    api.patch(
      `/api/v1/operator/products/${productId}/images/${imageId}/set-main`,
    ),

  sortImages: (productId: number, imageIds: number[]) =>
    api.patch(
      `/api/v1/operator/products/${productId}/images/sort`,
      imageIds,
    ),

  // 供货关系（挂 SKU）
  listSuppliers: (productId: number, skuId: number) =>
    api.get<SupplierRelationDetail[]>(
      `/api/v1/operator/products/${productId}/skus/${skuId}/suppliers`,
    ),

  addSupplier: (
    productId: number,
    skuId: number,
    data: Record<string, unknown>,
  ) =>
    api.post<{ id: number }>(
      `/api/v1/operator/products/${productId}/skus/${skuId}/suppliers`,
      data,
    ),

  updateSupplier: (
    productId: number,
    skuId: number,
    psId: number,
    data: Record<string, unknown>,
  ) =>
    api.put<{ id: number }>(
      `/api/v1/operator/products/${productId}/skus/${skuId}/suppliers/${psId}`,
      data,
    ),

  removeSupplier: (productId: number, skuId: number, psId: number) =>
    api.delete(
      `/api/v1/operator/products/${productId}/skus/${skuId}/suppliers/${psId}`,
    ),
};

// ── 品类属性模板 ────────────────────────────────────────

export const categoryApi = {
  attrTemplates: (code: string) =>
    api.get<AttrTemplate[]>(
      `/api/v1/operator/products/attr-templates/${code}`,
    ),
};
