// 央企/客户专区(Zone)买家侧只读 API client。
//
// 后端契约: backend/app/api/v1/zones.py
// 全部端点要求:已登录 + 持有该 zone 的 ZoneGrant,否则 403(不区分"不存在"/"未授权")。
// 列表/详情复用公开商品序列化,类型直接借用 lib/api/products.ts 里的公开商品类型。

import { api } from "../api";
import type { ProductListResponse, ProductPublicDetail } from "./products";

export interface ZoneCategory {
  id: number;
  code: string;
  /** 后端按 Accept-Language 填充的本地化名称 */
  name: string;
  name_zh: string;
  name_en: string | null;
  sort_order: number;
}

export interface ZoneProductListParams {
  zone_category_code?: string;
  keyword?: string;
  spec?: string;
  page?: number;
  size?: number;
}

/** 专区商品详情 — 公开详情字段集合 + SKU 变体(供换购用) */
export interface ZoneProductDetail extends ProductPublicDetail {
  skus: NonNullable<ProductPublicDetail["skus"]>;
}

export const zonesApi = {
  /** 专区客户视角大类导航 */
  categories: (zoneCode: string) =>
    api.get<ZoneCategory[]>(`/api/v1/zones/${zoneCode}/categories`),

  /** 专区白名单商品列表(可按客户视角大类筛选) */
  products: (zoneCode: string, params: ZoneProductListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.zone_category_code) qs.set("zone_category_code", params.zone_category_code);
    if (params.keyword) qs.set("keyword", params.keyword);
    if (params.spec) qs.set("spec", params.spec);
    if (params.page) qs.set("page", String(params.page));
    if (params.size) qs.set("size", String(params.size));
    const q = qs.toString();
    return api.get<ProductListResponse>(`/api/v1/zones/${zoneCode}/products${q ? `?${q}` : ""}`);
  },

  /** 专区商品详情(含可换购 SKU 变体) */
  product: (zoneCode: string, productId: number) =>
    api.get<ZoneProductDetail>(`/api/v1/zones/${zoneCode}/products/${productId}`),
};
