// 买方浏览偏好 API
import { api } from "../api";

/** 获取当前买方的浏览偏好品类 codes */
export async function getBrowsePreferences(): Promise<string[]> {
  const res = await api.get<{ category_codes: string[] }>("/api/v1/buyer/browse-preferences");
  return res.category_codes;
}

/** 替换浏览偏好品类 */
export async function replaceBrowsePreferences(
  categoryCodes: string[],
): Promise<string[]> {
  const res = await api.put<{ category_codes: string[] }>("/api/v1/buyer/browse-preferences", {
    category_codes: categoryCodes,
  });
  return res.category_codes;
}
