import { create } from "zustand";
import type { MeData, RoleCode } from "@/lib/auth";

interface AuthState {
  /** access token 仅存内存,刷新页面通过 refresh cookie 静默续期 */
  accessToken: string | null;
  user: MeData | null;
  loaded: boolean;

  setAccessToken: (t: string | null) => void;
  setUser: (u: MeData | null) => void;
  setLoaded: (b: boolean) => void;
  /** 清掉所有 auth 状态(登出 / refresh 失败 用)*/
  clear: () => void;
  /** 向后兼容旧 API,等同 clear() + setLoaded(true) */
  reset: () => void;

  hasPermission: (code: string) => boolean;
  hasRole: (code: RoleCode) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  loaded: false,
  setAccessToken: (t) => set({ accessToken: t }),
  setUser: (u) => set({ user: u }),
  setLoaded: (b) => set({ loaded: b }),
  clear: () => set({ accessToken: null, user: null }),
  reset: () => set({ accessToken: null, user: null, loaded: true }),
  hasPermission: (code) => {
    const u = get().user;
    return !!u && u.permissions.includes(code);
  },
  hasRole: (code) => {
    const u = get().user;
    return !!u && u.roles.includes(code);
  },
}));
