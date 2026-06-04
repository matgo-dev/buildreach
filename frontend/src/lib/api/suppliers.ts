// /api/v1/suppliers 客户端
//
// 后端契约见 backend/app/api/v1/suppliers.py

import { api } from "../api";

export type Grade = "A" | "B" | "C" | "D";

export interface SupplierListItem {
  id: number;
  name: string;
  country_code: string;
  status: string;
  total_score: number | null;
  grade: Grade | null;
}

export const suppliersApi = {
  /** 供应商目录列表(关键词 / 国别 / 级别筛选)。 */
  list: (params: { q?: string; country?: string; grade?: string }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.country) qs.set("country", params.country);
    if (params.grade) qs.set("grade", params.grade);
    const query = qs.toString();
    return api.get<SupplierListItem[]>(
      `/api/v1/suppliers${query ? `?${query}` : ""}`
    );
  },
};
