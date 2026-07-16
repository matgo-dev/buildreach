// 运营 Banner 管理 API 客户端 — CRUD + 图片上传
import { api } from "../api";
import { useAuthStore } from "@/stores/authStore";
import { getApiBase } from "@/lib/env";

const PREFIX = "/api/v1/operator/banners";

/** 管理接口返回(含全部字段)。image_url 为相对 key,image_full_url 供预览 */
export interface BannerAdmin {
  id: number;
  title_zh: string | null;
  title_en: string | null;
  title_sw: string | null;
  image_url: string;       // 相对 key(banners/xxx.jpg),回传给创建/更新
  image_full_url: string | null; // 完整路径,仅预览用
  link_url: string | null;
  sort_order: number;
  is_active: boolean;
  position: string;
  start_at: string | null;
  end_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BannerWriteInput {
  title_zh?: string | null;
  title_en?: string | null;
  title_sw?: string | null;
  image_url?: string;
  link_url?: string | null;
  sort_order?: number;
  is_active?: boolean;
  position?: string;
}

export interface BannerUploadResult {
  image_url: string;   // 相对 key,提交到创建/更新
  full_url: string;    // 完整路径,预览用
}

export const operatorBannersApi = {
  /** 列表(含未启用),可按 position 筛选 */
  list: (position?: string) =>
    api.get<BannerAdmin[]>(`${PREFIX}${position ? `?position=${encodeURIComponent(position)}` : ""}`),

  /** 创建 */
  create: (data: BannerWriteInput) => api.post<BannerAdmin>(PREFIX, data),

  /** 更新 */
  update: (id: number, data: BannerWriteInput) => api.put<BannerAdmin>(`${PREFIX}/${id}`, data),

  /** 删除 */
  remove: (id: number) => api.delete(`${PREFIX}/${id}`),

  /** 上传图片（multipart），返回相对 key + 预览 URL */
  uploadImage: async (file: File): Promise<BannerUploadResult> => {
    const formData = new FormData();
    formData.append("file", file);

    const token = useAuthStore.getState().accessToken;
    const lang = typeof document !== "undefined" ? document.documentElement.lang || "zh" : "zh";

    const res = await fetch(`${getApiBase()}${PREFIX}/upload`, {
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
      throw new Error(json.message ?? "Banner image upload failed");
    }
    return json.data as BannerUploadResult;
  },
};
