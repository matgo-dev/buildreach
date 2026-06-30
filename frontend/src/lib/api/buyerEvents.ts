// 买方行为事件 API client
//
// 后端契约: backend/app/api/v1/buyer_events.py

import { api } from "../api";

// ---------- 类型 ----------

export interface RecentViewProduct {
  id: number;
  name: string;
  main_image: string | null;
  main_image_thumbnail: string | null;
  category_code: string | null;
  unit: string | null;
  moq: number | null;
}

// ---------- 买方端点 ----------

export async function getRecentViews(limit = 8): Promise<RecentViewProduct[]> {
  return api.get(`/api/v1/buyer/events/recent-views?limit=${limit}`);
}

export async function getRecentSearches(limit = 10): Promise<string[]> {
  return api.get(`/api/v1/buyer/events/recent-searches?limit=${limit}`);
}

export async function removeRecentView(productId: number): Promise<{ deleted: number }> {
  return api.delete(`/api/v1/buyer/events/recent-views/${productId}`);
}

export async function clearRecentSearches(): Promise<{ deleted: number }> {
  return api.delete("/api/v1/buyer/events/recent-searches");
}
