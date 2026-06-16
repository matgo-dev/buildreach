// 买方浏览偏好 API
import { api } from "../api";

/** 获取当前买方的浏览偏好品类 codes */
export async function getBrowsePreferences(): Promise<string[]> {
  return api.get<string[]>("/api/v1/buyer/browse-preferences");
}

/** 替换浏览偏好品类 */
export async function replaceBrowsePreferences(
  categoryCodes: string[],
): Promise<string[]> {
  return api.put<string[]>("/api/v1/buyer/browse-preferences", {
    category_codes: categoryCodes,
  });
}
