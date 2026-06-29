import { create } from "zustand";

export interface ContactContext {
  /** 商品名称（拼 WhatsApp 预填文案用） */
  productName?: string;
  /** 商品编号 */
  productCode?: string;
}

interface ContactStore {
  isOpen: boolean;
  context: ContactContext | null;
  open: (ctx?: ContactContext) => void;
  close: () => void;
}

export const useContactStore = create<ContactStore>((set) => ({
  isOpen: false,
  context: null,
  open: (ctx) => set({ isOpen: true, context: ctx ?? null }),
  close: () => set({ isOpen: false, context: null }),
}));
