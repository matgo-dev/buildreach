// /api/v1/categories 客户端
//
// 后端契约见 backend/app/api/v1/categories.py
// PRD: docs/商品三级分类-PRD-v1.0.md §5

import { api } from "../api";

export interface CategoryNode {
  id: number;
  code: string;
  name_zh: string;
  name_en: string | null;
  name: string; // 后端按 Accept-Language 填充的本地化名称
  level: 1 | 2 | 3;
  parent_code: string | null;
  sort_order: number;
  is_leaf: boolean;
}

export interface CategoryTreeNode {
  id: number;
  code: string;
  name_zh: string;
  name_en: string | null;
  name: string; // 后端按 Accept-Language 填充的本地化名称
  short_name: string | null; // 导航栏简称(按 locale 填充)
  level: 1 | 2 | 3;
  /** 无 active 子节点时为 true（后端维护，不要靠 children.length 判断叶子） */
  is_leaf: boolean;
  children: CategoryTreeNode[];
}

export const categoriesApi = {
  /** 扁平列表;is_active 默认 true。 */
  list: (params?: { level?: 1 | 2 | 3; parent_code?: string; is_active?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.level !== undefined) qs.set("level", String(params.level));
    if (params?.parent_code !== undefined) qs.set("parent_code", params.parent_code);
    if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
    const q = qs.toString();
    return api.get<CategoryNode[]>(`/api/v1/categories${q ? `?${q}` : ""}`);
  },
  /** 嵌套树;is_active 默认 true, max_depth 限制层级深度。 */
  tree: (params?: { is_active?: boolean; max_depth?: number }) => {
    const qs = new URLSearchParams();
    if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
    if (params?.max_depth !== undefined) qs.set("max_depth", String(params.max_depth));
    const q = qs.toString();
    return api.get<CategoryTreeNode[]>(`/api/v1/categories/tree${q ? `?${q}` : ""}`);
  },
};
