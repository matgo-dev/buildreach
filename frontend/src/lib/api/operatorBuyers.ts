// 运营端 — 买方组织搜索 API
import { api } from "../api";

export interface BuyerOrgBrief {
  id: number;
  name: string;
  code: string | null;
  unified_social_credit_code?: string | null;
}

export interface BuyerOrgListResponse {
  items: BuyerOrgBrief[];
  total: number;
  page: number;
  page_size: number;
}

export async function searchBuyerOrgs(
  q: string = "",
  page: number = 1,
  pageSize: number = 20,
): Promise<BuyerOrgListResponse> {
  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  qs.set("page", String(page));
  qs.set("page_size", String(pageSize));
  return api.get<BuyerOrgListResponse>(`/api/v1/operator/buyer-orgs?${qs.toString()}`);
}
