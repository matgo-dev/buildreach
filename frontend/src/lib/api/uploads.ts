// 文件上传 API — 通用上传端点，供询价附件等场景复用
import { getToken } from "@/lib/api";
import { getApiBase } from "@/lib/env";

export interface UploadResult {
  url: string;
  filename: string;
}

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

/** 返回 i18n key，null 表示校验通过 */
export function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.has(file.type)) return "attachment.invalidType";
  const max = IMAGE_TYPES.has(file.type) ? MAX_SIZE_IMAGE : MAX_SIZE_DOC;
  if (file.size > max) return "attachment.tooLarge";
  return null;
}

export async function uploadFile(file: File): Promise<UploadResult> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${getApiBase()}/api/v1/uploads/files`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.message || `Upload failed: ${resp.status}`);
  }
  const json = await resp.json();
  return json.data as UploadResult;
}
