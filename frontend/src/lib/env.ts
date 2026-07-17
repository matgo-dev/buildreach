// 运行时环境变量读取。
//
// 容器启动时 entrypoint.sh 生成 public/__env.js，注入 window.__ENV。
// 浏览器侧优先读 window.__ENV，SSR/开发时 fallback 到 process.env。

declare global {
  interface Window {
    __ENV?: {
      API_BASE_URL?: string;
      FLOOR_ASSET_VERSION?: string;
    };
  }
}

/**
 * 获取 API 基础地址（浏览器访问后端的公网地址）。
 *
 * 优先级：window.__ENV.API_BASE_URL > process.env.API_BASE_URL > process.env.NEXT_PUBLIC_API_BASE_URL
 * 未配置时抛错，不提供默认值，避免静默连错端口。
 */
export function getApiBase(): string {
  if (typeof window !== "undefined" && window.__ENV?.API_BASE_URL) {
    return window.__ENV.API_BASE_URL;
  }
  const base = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) {
    throw new Error("API_BASE_URL 未配置，请在 .env.local 中设置 API_BASE_URL");
  }
  return base;
}

export function getFloorAssetVersion(): string {
  const version =
    typeof window !== "undefined"
      ? window.__ENV?.FLOOR_ASSET_VERSION
      : process.env.FLOOR_ASSET_VERSION || process.env.NEXT_PUBLIC_FLOOR_ASSET_VERSION;
  return version?.trim() ?? "";
}

function appendQueryParam(url: string, key: string, value: string): string {
  if (!url || !value) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
}

/**
 * 将后端返回的相对图片路径（/static/...）拼成完整 URL。
 *
 * 已是绝对 URL（http/https 开头）则原样返回，兼容历史数据。
 */
export function imageUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${getApiBase()}${path}`;
}

export function floorImageUrl(path: string | null | undefined): string {
  return appendQueryParam(imageUrl(path), "v", getFloorAssetVersion());
}
