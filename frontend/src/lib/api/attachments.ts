/**
 * 附件 API — 鉴权上传 + 鉴权 blob 下载。
 *
 * 上传:multipart/form-data → 返回 AttachmentPublic(含 id)
 * 下载:fetch blob(带 token) → Blob → createObjectURL(前端自行管理 revoke)
 */
import { getToken } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export interface AttachmentPublic {
  id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  download_url: string;
  thumbnail_url: string | null;
}

// ── 前端校验(与后端允许族对齐) ──

const ALLOWED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
]);
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_SIZE_IMAGE = 5 * 1024 * 1024;
const MAX_SIZE_DOC = 10 * 1024 * 1024;
export const MAX_ATTACHMENTS = 6;

/** 返回 i18n key(rfq namespace),null 表示校验通过 */
export function validateFile(file: File): string | null {
  // 扩展名检查(浏览器 MIME 不可靠时兜底)
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const allowedExts = new Set([".jpg", ".jpeg", ".png", ".webp", ".pdf", ".xlsx", ".xls"]);
  if (!ALLOWED_TYPES.has(file.type) && !allowedExts.has(ext)) {
    return "attachment.invalidType";
  }
  const max = IMAGE_TYPES.has(file.type) ? MAX_SIZE_IMAGE : MAX_SIZE_DOC;
  if (file.size > max) return "attachment.tooLarge";
  return null;
}

// ── 上传 ──

export async function uploadAttachment(file: File): Promise<AttachmentPublic> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${API_BASE}/api/v1/attachments`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
    body: form,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.message || `Upload failed: ${resp.status}`);
  }
  const json = await resp.json();
  return json.data as AttachmentPublic;
}

// ── 鉴权缩略图 ──

export async function fetchThumbnailBlob(id: number): Promise<Blob> {
  const token = getToken();
  const resp = await fetch(`${API_BASE}/api/v1/attachments/${id}/thumbnail`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  if (!resp.ok) {
    throw new Error(`Thumbnail failed: ${resp.status}`);
  }
  return resp.blob();
}

// ── 鉴权 blob 下载 ──

export async function fetchAttachmentBlob(id: number): Promise<Blob> {
  const token = getToken();
  const resp = await fetch(`${API_BASE}/api/v1/attachments/${id}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  if (!resp.ok) {
    throw new Error(`Download failed: ${resp.status}`);
  }
  return resp.blob();
}

/** 触发浏览器下载(鉴权 fetch → blob → anchor click) */
export async function downloadAttachment(id: number, filename: string): Promise<void> {
  const blob = await fetchAttachmentBlob(id);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── 工具 ──

const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp"]);

export function isImageContentType(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export function isImageFilename(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return IMAGE_EXTS.has(ext);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
