// 买方询价篮 API client
//
// 后端契约: backend/app/api/v1/cart.py
// 所有接口返回 { code, message, data: CartPublic }

import { api } from "../api";

// ---------- 类型 ----------

export interface CartItemPublic {
  item_id: number;
  sku_id: number;
  product_id: number;
  quantity: number;
  sku_code: string;
  sku_name: string | null;
  product_name: string | null;
  manufacturer_model: string | null;
  color: string | null;
  material: string | null;
  unit: string | null;
  moq: number | null;
  is_purchasable: boolean;
  unavailable_reason: string | null; // SKU_DELETED | SKU_INACTIVE | PRODUCT_DELETED | PRODUCT_INACTIVE
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

/** 加入询价篮（同 SKU 自动累加数量） */
export async function addCartItem(
  skuId: number,
  quantity: number
): Promise<CartPublic> {
  return api.post<CartPublic>("/api/v1/cart/items", {
    sku_id: skuId,
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
