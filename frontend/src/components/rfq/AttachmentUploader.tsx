"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, X, FileText, Upload, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import { uploadFile, validateFile, MAX_ATTACHMENTS } from "@/lib/api/uploads";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp"]);

function isImageUrl(url: string): boolean {
  const ext = url.slice(url.lastIndexOf(".")).toLowerCase();
  return IMAGE_EXTS.has(ext);
}

interface AttachmentUploaderProps {
  urls: string[];
  onChange: (urls: string[]) => void;
}

export default function AttachmentUploader({
  urls,
  onChange,
}: AttachmentUploaderProps) {
  const t = useTranslations("rfq");
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const isFull = urls.length >= MAX_ATTACHMENTS;

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (uploading) return;
      if (!files || files.length === 0) return;

      const remaining = MAX_ATTACHMENTS - urls.length;
      if (remaining <= 0) {
        toast.error(t("attachment.maxReached"));
        return;
      }

      const toUpload = Array.from(files).slice(0, remaining);
      setUploading(true);

      const newUrls: string[] = [];
      for (const file of toUpload) {
        const err = validateFile(file);
        if (err) {
          // validateFile 返回 i18n key，直接翻译后提示
          toast.error(t(err as Parameters<typeof t>[0]));
          continue;
        }
        try {
          const result = await uploadFile(file);
          newUrls.push(result.url);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : String(e));
        }
      }
      if (newUrls.length > 0) {
        onChange([...urls, ...newUrls]);
      }
      setUploading(false);
      // 清空 input 以允许重新选相同文件
      if (inputRef.current) inputRef.current.value = "";
    },
    [urls, onChange, toast, t],
  );

  const handleRemove = useCallback(
    (idx: number) => {
      onChange(urls.filter((_, i) => i !== idx));
    },
    [urls, onChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Paperclip className="h-4 w-4 text-gray-400" />
        <span className="text-sm font-medium text-gray-700">
          {t("attachment.label")} ({urls.length}/{MAX_ATTACHMENTS})
        </span>
      </div>

      {urls.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {urls.map((url, idx) => (
            <div key={url} className="group relative">
              {isImageUrl(url) ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`${API_BASE}${url}`}
                  alt=""
                  className="h-20 w-20 rounded-lg border border-gray-200 object-cover"
                />
              ) : (
                <div className="flex h-20 w-20 flex-col items-center justify-center rounded-lg border border-gray-200 bg-gray-50">
                  <FileText className="h-6 w-6 text-gray-400" />
                  <span className="mt-1 truncate w-full px-1 text-center text-[10px] text-gray-400">
                    {url.split("/").pop()?.slice(-12) ?? "file"}
                  </span>
                </div>
              )}
              <button
                type="button"
                onClick={() => handleRemove(idx)}
                aria-label="Remove"
                className="absolute -right-1.5 -top-1.5 hidden rounded-full bg-red-500 p-0.5 text-white shadow-sm group-hover:block"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {!isFull && (
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
          className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-200 py-4 text-sm text-gray-400 transition-colors hover:border-[#00505a]/40 hover:text-gray-500"
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          <span>{t("attachment.upload")}</span>
        </div>
      )}
      <p className="text-xs text-gray-400">{t("attachment.hint")}</p>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".jpg,.jpeg,.png,.webp,.pdf,.xlsx,.xls"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
