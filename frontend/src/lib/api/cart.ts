// 买方询价篮 API client
//
// 后端契约: backend/app/api/v1/cart.py
// 所有接口返回 { code, message, data: CartPublic }

import { api } from "../api";

// ---------- 类型 ----------

export interface CartItemPublic {
  item_id: number;
  product_id: number;
  sku_id: number | null;                                          // 历史兼容
  selected_variants: Array<{ attr_name: string; value: string }>;
  quantity: number;
  product_name: string | null;
  variant_display: string | null;
  description: string | null;
  brand: string | null;
  origin: string | null;
  unit: string | null;
  moq: number | null;
  supply_mode: string | null;
  certifications: string[];
  lead_time_min: number | null;
  lead_time_max: number | null;
  category_name: string | null;
  is_purchasable: boolean;
  unavailable_reason: string | null;
  // 可能的值: PRODUCT_DELETED | PRODUCT_INACTIVE | VARIANT_UNAVAILABLE
  main_image: string | null;
}

export interface CartPublic {
  id: number | null;
  items: CartItemPublic[];
}

// ---------- API 函数 ----------

/** 获取当前用户询价篮 */
export async function getCart(): Promise<CartPublic> {
  return api.get<CartPublic>("/api/v1/cart");
}

/** 加入询价篮（同 SPU + 相同变体自动累加数量） */
export async function addCartItem(
  productId: number,
  selectedVariants: Array<{ attr_name: string; value: string }>,
  quantity: number,
): Promise<CartPublic> {
  return api.post<CartPublic>("/api/v1/cart/items", {
    product_id: productId,
    selected_variants: selectedVariants,
    quantity,
  });
}

/** 修改询价篮项数量 */
export async function updateCartItem(
  itemId: number,
  quantity: number
): Promise<CartPublic> {
  return api.patch<CartPublic>(`/api/v1/cart/items/${itemId}`, { quantity });
}

/** 删除单个询价篮项 */
export async function removeCartItem(itemId: number): Promise<CartPublic> {
  return api.delete<CartPublic>(`/api/v1/cart/items/${itemId}`);
}

/** 清空询价篮 */
export async function clearCart(): Promise<CartPublic> {
  return api.delete<CartPublic>("/api/v1/cart/items");
}
