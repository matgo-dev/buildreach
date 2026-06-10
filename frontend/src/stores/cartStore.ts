import { create } from "zustand";
import type { CartPublic } from "@/lib/api/cart";

interface CartState {
  /** 角标数字：可购 SKU 行数（不是 quantity 总和） */
  count: number;
  /** 自增触发询价篮页面 SWR revalidate */
  refreshFlag: number;

  /** 从 CartPublic 直接算出可购行数并更新 count */
  syncFromCart: (cart: CartPublic) => void;
  /** 自增 refreshFlag，触发依赖它的 SWR 重新请求 */
  triggerRefresh: () => void;
}

export const useCartStore = create<CartState>((set) => ({
  count: 0,
  refreshFlag: 0,

  syncFromCart: (cart) => {
    const purchasableCount = cart.items.filter(
      (i) => i.is_purchasable
    ).length;
    set({ count: purchasableCount });
  },

  triggerRefresh: () =>
    set((s) => ({ refreshFlag: s.refreshFlag + 1 })),
}));
