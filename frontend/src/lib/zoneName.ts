/** 专区摘要(/auth/me 的 zones 项、GET /zones 的列表项)。 */
export interface ZoneBriefForUser {
  code: string;
  name_zh: string;
  name_en: string | null;
}

/** 专区显示名:中文用 name_zh,其它语种优先 name_en,缺失回退中文。导航与专区页头共用,口径唯一。 */
export function zoneDisplayName(z: ZoneBriefForUser, locale: string): string {
  return locale === "zh" ? z.name_zh : z.name_en || z.name_zh;
}
