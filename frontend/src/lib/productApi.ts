/**
 * 商品模块 API 封装。
 */
import { api } from "./api";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// ── 类型 ──────────────────────────────────────────────────

export interface ProductPublic {
  id: number;
  sku_code: string;
  name: string;
  category_code: string;
  category_name: string;
  price_min: number;
  price_max: number;
  currency: string;
  unit: string;
  moq: number;
  lead_time_days: number | null;
  origin: string;
  brand: string | null;
  certifications: string[];
  is_featured: boolean;
  main_image: string | null;
}

export interface ProductOperator extends ProductPublic {
  name_i18n: Record<string, string> | null;
  status: string;
  created_by_name: string;
  supplier_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductImage {
  id: number;
  url: string;
  sort_order: number;
}

export interface ProductAttr {
  attr_key: string;
  attr_value: string;
  attr_unit: string | null;
  sort_order: number;
}

export interface ProductSupplierDetail {
  id: number;
  product_id: number;
  supplier_org_id: number;
  supplier_org_name: string;
  supplier_price: number;
  supplier_moq: number | null;
  supplier_lead_time_days: number | null;
  has_pvoc: boolean;
  has_coc: boolean;
  is_preferred: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductOperatorDetail extends ProductPublic {
  name_i18n: Record<string, string> | null;
  description: string | null;
  description_i18n: Record<string, string> | null;
  hs_code: string | null;
  status: string;
  created_by_name: string;
  images: ProductImage[];
  attributes: ProductAttr[];
  suppliers: ProductSupplierDetail[];
  created_at: string;
  updated_at: string;
}

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

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── 公开接口 ──────────────────────────────────────────────

export const publicProductApi = {
  list: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return api.get<PageResult<ProductPublic>>(`/api/v1/products?${qs}`);
  },
  detail: (id: number) => api.get<ProductPublic>(`/api/v1/products/${id}`),
};

// ── 运营接口 ──────────────────────────────────────────────

export const operatorProductApi = {
  list: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    return api.get<PageResult<ProductOperator>>(`/api/v1/operator/products?${qs}`);
  },

  detail: (id: number) =>
    api.get<ProductOperatorDetail>(`/api/v1/operator/products/${id}`),

  create: (data: Record<string, unknown>) =>
    api.post<{ id: number; sku_code: string }>("/api/v1/operator/products", data),

  update: (id: number, data: Record<string, unknown>) =>
    api.put<{ id: number }>(`/api/v1/operator/products/${id}`, data),

  updateStatus: (id: number, status: string) =>
    api.patch<{ id: number; status: string }>(
      `/api/v1/operator/products/${id}/status`,
      { status },
    ),

  delete: (id: number) => api.delete(`/api/v1/operator/products/${id}`),

  // 图片
  uploadImage: async (productId: number, file: File): Promise<ProductImage> => {
    const { useAuthStore } = await import("@/stores/authStore");
    const token = useAuthStore.getState().accessToken;
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(
      `${BASE}/api/v1/operator/products/${productId}/images`,
      {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      },
    );
    const json = await res.json();
    if (!res.ok || json.code !== 0) throw new Error(json.message || "Upload failed");
    return json.data;
  },

  deleteImage: (productId: number, imageId: number) =>
    api.delete(`/api/v1/operator/products/${productId}/images/${imageId}`),

  sortImages: (productId: number, imageIds: number[]) =>
    api.patch(`/api/v1/operator/products/${productId}/images/sort`, imageIds),

  // 供货关系
  listSuppliers: (productId: number) =>
    api.get<ProductSupplierDetail[]>(
      `/api/v1/operator/products/${productId}/suppliers`,
    ),

  addSupplier: (productId: number, data: Record<string, unknown>) =>
    api.post<{ id: number }>(
      `/api/v1/operator/products/${productId}/suppliers`,
      data,
    ),

  updateSupplier: (
    productId: number,
    psId: number,
    data: Record<string, unknown>,
  ) =>
    api.put<{ id: number }>(
      `/api/v1/operator/products/${productId}/suppliers/${psId}`,
      data,
    ),

  removeSupplier: (productId: number, psId: number) =>
    api.delete(`/api/v1/operator/products/${productId}/suppliers/${psId}`),
};

// ── 品类属性模板 ──────────────────────────────────────────

export const categoryApi = {
  attrTemplates: (code: string) =>
    api.get<AttrTemplate[]>(`/api/v1/categories/${code}/attr-templates`),
};
