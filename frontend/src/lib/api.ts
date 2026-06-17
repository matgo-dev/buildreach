// 统一的 fetch 封装。
//
// 设计要点(token 存储重构后):
//   - access token 从 Zustand 内存读(不再 localStorage)
//   - refresh token 在 httpOnly cookie,浏览器自动带,JS 读不到
//   - credentials: "include" 让浏览器把 cookie 发出去
//   - 401 自动调 /auth/refresh 拿新 access 后重试一次
//   - 并发请求触发的多次 refresh 用 promise 复用去重

import { useAuthStore } from "@/stores/authStore";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const REFRESH_PATH = "/api/v1/auth/refresh";

export class ApiError extends Error {
  code: number;
  status: number;
  traceId?: string;
  data?: unknown;
  messageKey?: string;
  messageParams?: Record<string, unknown>;

  constructor(opts: { code: number; message: string; status: number; traceId?: string; data?: unknown; messageKey?: string; messageParams?: Record<string, unknown> }) {
    super(opts.message);
    this.code = opts.code;
    this.status = opts.status;
    this.traceId = opts.traceId;
    this.data = opts.data;
    this.messageKey = opts.messageKey;
    this.messageParams = opts.messageParams;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** 跳过 Authorization 注入(用于登录)*/
  noAuth?: boolean;
  /** 跳过 401 自动 refresh 重试(refresh 接口自身用)*/
  noRefreshRetry?: boolean;
  /** 内部使用:已经是重试请求,不再递归 */
  _isRetry?: boolean;
};

// ---------- refresh 单例(并发去重)----------
let refreshPromise: Promise<boolean> | null = null;

/** 调 /auth/refresh 续期。返回是否成功。并发去重。*/
export async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${BASE}${REFRESH_PATH}`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return false;
      const json = await res.json();
      const access = json?.data?.access_token;
      if (!access) return false;
      useAuthStore.getState().setAccessToken(access);
      return true;
    } catch {
      return false;
    } finally {
      // 留一小段时间让并发 batch 走完同一个 promise,再清
      setTimeout(() => {
        refreshPromise = null;
      }, 0);
    }
  })();

  return refreshPromise;
}

// ---------- Session ID（标签页级会话标识）----------

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = sessionStorage.getItem("x-session-id");
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem("x-session-id", sid);
  }
  return sid;
}

// ---------- 主请求函数 ----------

async function rawFetch(path: string, opts: RequestOptions): Promise<Response> {
  const { body, noAuth, headers, _isRetry, noRefreshRetry, ...rest } = opts;
  void _isRetry;
  void noRefreshRetry;

  // Accept-Language 从 <html lang="..."> 读取(由 next-intl locale layout 设置)
  const lang = typeof document !== "undefined" ? document.documentElement.lang || "zh" : "zh";
  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "Accept-Language": lang,
    ...(headers as Record<string, string> | undefined),
  };
  // 会话追踪
  const sid = getSessionId();
  if (sid) finalHeaders["X-Session-Id"] = sid;

  if (!noAuth) {
    const token = useAuthStore.getState().accessToken;
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  return fetch(`${BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    credentials: "include", // refresh cookie 自动带
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiRequest<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res = await rawFetch(path, opts);

  // 401 → 尝试 refresh + 重试一次
  if (res.status === 401 && !opts.noRefreshRetry && !opts._isRetry && !opts.noAuth) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      res = await rawFetch(path, { ...opts, _isRetry: true });
    } else {
      // refresh 也失败 → 清状态,让上层(AuthProvider / RouteGuard)处理跳转
      useAuthStore.getState().clear();
    }
  }

  const traceId = res.headers.get("X-Trace-Id") || undefined;

  let json: any = null;
  try {
    json = await res.json();
  } catch {
    /* 非 JSON 响应,保持 null */
  }

  if (!res.ok) {
    throw new ApiError({
      code: json?.code ?? res.status * 100,
      message: json?.message ?? res.statusText ?? "Request failed",
      status: res.status,
      traceId: json?.trace_id ?? traceId,
      data: json?.data,
      messageKey: json?.message_key,
      messageParams: json?.message_params,
    });
  }

  if (json && typeof json === "object" && "code" in json) {
    if (json.code !== 0) {
      throw new ApiError({
        code: json.code,
        message: json.message,
        status: res.status,
        traceId: json.trace_id ?? traceId,
        data: json.data,
        messageKey: json.message_key,
        messageParams: json.message_params,
      });
    }
    return json.data as T;
  }
  return json as T;
}

export const api = {
  get: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "POST", body }),
  put: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PUT", body }),
  patch: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "DELETE" }),
};

// ---------- 兼容旧 import:导出空实现避免编译失败 ----------
// 旧代码引用了 getToken / setTokens / clearTokens(基于 localStorage),
// 全部改成对 Zustand accessToken 的操作。
export function getToken(): string | null {
  return useAuthStore.getState().accessToken;
}
export function setTokens(access: string, _refresh: string) {
  void _refresh; // refresh 通过 cookie,JS 无需也无法存
  useAuthStore.getState().setAccessToken(access);
}
export function clearTokens() {
  useAuthStore.getState().setAccessToken(null);
}
