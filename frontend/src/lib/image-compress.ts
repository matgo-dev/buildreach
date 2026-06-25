/**
 * 前端图片自动压缩：手机拍照 10-20MB 也能无感上传。
 * 用 canvas 缩放 + quality 调整，压到 targetSize 以内。
 */

const DEFAULT_TARGET_SIZE = 2 * 1024 * 1024; // 2MB
const DEFAULT_MAX_DIMENSION = 2048; // 最大边长

/**
 * 压缩图片文件。如果文件已经小于 targetSize，直接返回原文件。
 * 仅支持 image/jpeg、image/png、image/webp，其他格式直接返回原文件。
 */
export async function compressImage(
  file: File,
  options?: { targetSize?: number; maxDimension?: number },
): Promise<File> {
  const targetSize = options?.targetSize ?? DEFAULT_TARGET_SIZE;
  const maxDimension = options?.maxDimension ?? DEFAULT_MAX_DIMENSION;

  // 已经够小，不压缩
  if (file.size <= targetSize) return file;

  // 非图片格式不处理
  if (!file.type.startsWith("image/")) return file;

  const bitmap = await createImageBitmap(file);
  let { width, height } = bitmap;

  // 等比缩放到 maxDimension 以内
  if (width > maxDimension || height > maxDimension) {
    const ratio = Math.min(maxDimension / width, maxDimension / height);
    width = Math.round(width * ratio);
    height = Math.round(height * ratio);
  }

  const canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;

  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  // 逐步降低 quality 直到满足大小要求
  const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
  let quality = 0.85;
  let blob: Blob;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    blob = await canvas.convertToBlob({ type: outputType, quality });
    if (blob.size <= targetSize || quality <= 0.3) break;
    quality -= 0.1;
  }

  // 压缩后比原文件还大，返回原文件
  if (blob.size >= file.size) return file;

  return new File([blob], file.name, { type: outputType, lastModified: Date.now() });
}

/**
 * 批量压缩多个图片文件。
 */
export async function compressImages(
  files: File[],
  options?: { targetSize?: number; maxDimension?: number },
): Promise<File[]> {
  return Promise.all(files.map((f) => compressImage(f, options)));
}
