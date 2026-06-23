// /api/v1/banners 客户端
import { api } from "../api";

export interface BannerSlide {
  id: number;
  title: string | null;
  image_url: string;
  link_url: string | null;
  sort_order: number;
  position: string;
}

export const bannersApi = {
  /** 获取指定位置的启用 Banner 列表(公开) */
  list: (position = "home_carousel") =>
    api.get<BannerSlide[]>(`/api/v1/banners?position=${encodeURIComponent(position)}`),
};
