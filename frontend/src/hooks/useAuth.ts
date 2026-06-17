"use client";
import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

import { authApi } from "@/lib/auth";
import { clearTokens, tryRefresh } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";
import { preferenceToLocale } from "@/i18n/locale-utils";
import { routing } from "@/i18n/routing";

const LEGACY_KEYS = ["ovx_access_token", "ovx_refresh_token"] as const;

function clearLegacyLocalStorage() {
  if (typeof window === "undefined") return;
  for (const k of LEGACY_KEYS) {
    try {
      localStorage.removeItem(k);
    } catch {
      /* ignore */
    }
  }
}

/**
 * 拼接带 locale 前缀的路径。
 * 默认语言(zh)不带前缀(localePrefix: "as-needed"),其他语言加 /en 等前缀。
 */
function localePrefix(path: string, locale: string): string {
  if (locale === routing.defaultLocale) return path;
  return `/${locale}${path}`;
}

/**
 * 应用启动:
 *   1. 清掉旧版 localStorage token(向后兼容)
 *   2. 调 /auth/refresh —— cookie 在则成功换 access,否则失败(返回 false)
 *   3. 成功 → 拉 /auth/me 写 Zustand;失败 → 标记 loaded
 */
export function useBootstrapAuth() {
  const { setUser, setLoaded, clear } = useAuthStore();

  useEffect(() => {
    clearLegacyLocalStorage();

    (async () => {
      const refreshed = await tryRefresh();
      if (!refreshed) {
        clear();
        setLoaded(true);
        return;
      }
      try {
        const me = await authApi.me();
        setUser(me);
      } catch {
        clear();
      } finally {
        setLoaded(true);
      }
    })();
  }, [setUser, setLoaded, clear]);
}

/**
 * 登录:
 *   1. 调 /auth/login → access 存内存
 *   2. 调 /auth/me → 拿用户信息(含 language_preference)
 *   3. 按 language_preference 决定目标 locale
 *   4. 跳转到目标 dashboard(带正确的 locale 前缀)
 *
 * 切 locale 用 window.location.href 硬跳转,确保翻译文件重新加载。
 * 同 locale 用 router.replace,走 client-side 导航更快。
 */
export function useLogin() {
  const router = useRouter();
  const currentLocale = useLocale();
  const setUser = useAuthStore((s) => s.setUser);
  const setLoaded = useAuthStore((s) => s.setLoaded);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);

  return async (identifier: string, password: string, phoneRegion?: string) => {
    const tokens = await authApi.login(identifier, password, phoneRegion);
    setAccessToken(tokens.access_token);
    const me = await authApi.me();
    setUser(me);
    setLoaded(true);

    const targetLocale = preferenceToLocale(me.language_preference);
    const targetPath = me.must_change_password
      ? "/change-password"
      : defaultDashboardOf(me.roles);

    if (targetLocale !== currentLocale) {
      // 切语言:硬跳转,确保 Next.js 重新加载对应 locale 的翻译文件
      window.location.href = localePrefix(targetPath, targetLocale);
    } else {
      // 同语言:client-side 导航
      router.replace(targetPath);
    }
  };
}

/** 登出:调 /auth/logout(后端清 cookie + 写审计)→ 清内存 → 跳 /login。*/
export function useLogout() {
  const router = useRouter();
  const clear = useAuthStore((s) => s.clear);

  return async () => {
    try {
      await authApi.logout();
    } catch {
      /* 后端失败也要本地登出 */
    }
    clear();
    clearTokens();
    router.replace("/login");
  };
}
