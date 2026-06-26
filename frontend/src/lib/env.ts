// 运行时环境变量读取。
//
// 容器启动时 entrypoint.sh 生成 public/__env.js，注入 window.__ENV。
// 浏览器侧优先读 window.__ENV，SSR/开发时 fallback 到 process.env。

declare global {
  interface Window {
    __ENV?: {
      API_BASE_URL?: string;
    };
  }
}

/**
 * 获取 API 基础地址（浏览器访问后端的公网地址）。
 *
 * 优先级：window.__ENV.API_BASE_URL > process.env.NEXT_PUBLIC_API_BASE_URL > localhost fallback
 */
export function getApiBase(): string {
  if (typeof window !== "undefined" && window.__ENV?.API_BASE_URL) {
    return window.__ENV.API_BASE_URL;
  }
  // SSR 或开发环境 fallback（NEXT_PUBLIC_ 构建时注入，仅 dev 有效）
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
}
