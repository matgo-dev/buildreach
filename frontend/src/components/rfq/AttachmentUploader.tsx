"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, X, FileText, Upload, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import {
  uploadAttachment,
  validateFile,
  fetchThumbnailBlob,
  isImageContentType,
  formatFileSize,
  MAX_ATTACHMENTS,
  type AttachmentPublic,
} from "@/lib/api/attachments";

interface AttachmentUploaderProps {
  /** 已关联的附件列表(id-based) */
  attachments: AttachmentPublic[];
  /** 回调:更新附件 id 列表 */
  onChange: (attachments: AttachmentPublic[]) => void;
}

export default function AttachmentUploader({
  attachments,
  onChange,
}: AttachmentUploaderProps) {
  const t = useTranslations("rfq");
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [lightboxId, setLightboxId] = useState<number | null>(null);

  // blob URL 缓存(图片缩略图)
  const [thumbUrls, setThumbUrls] = useState<Record<number, string>>({});
  const [thumbFailed, setThumbFailed] = useState<Set<number>>(new Set());

  const isFull = attachments.length >= MAX_ATTACHMENTS;

  // 加载图片缩略图
  useEffect(() => {
    let cancelled = false;
    const imageAtts = attachments.filter((a) => isImageContentType(a.content_type));

    for (const att of imageAtts) {
      if (thumbUrls[att.id] || thumbFailed.has(att.id)) continue;
      fetchThumbnailBlob(att.id)
        .then((blob) => {
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          setThumbUrls((prev) => ({ ...prev, [att.id]: url }));
        })
        .catch(() => {
          if (!cancelled) setThumbFailed((prev) => new Set(prev).add(att.id));
        });
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachments.map((a) => a.id).join(",")]);

  // 清理 blob URL
  useEffect(() => {
    return () => {
      Object.values(thumbUrls).forEach((url) => URL.revokeObjectURL(url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (uploading) return;
      if (!files || files.length === 0) return;

      const remaining = MAX_ATTACHMENTS - attachments.length;
      if (remaining <= 0) {
        toast.error(t("attachment.maxReached"));
        return;
      }

      const toUpload = Array.from(files).slice(0, remaining);
      setUploading(true);

      const newAtts: AttachmentPublic[] = [];
      for (const file of toUpload) {
        const err = validateFile(file);
        if (err) {
          toast.error(t(err as Parameters<typeof t>[0]));
          continue;
        }
        try {
          const result = await uploadAttachment(file);
          newAtts.push(result);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : String(e));
        }
      }
      if (newAtts.length > 0) {
        onChange([...attachments, ...newAtts]);
      }
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    },
    [attachments, onChange, toast, t, uploading],
  );

  const handleRemove = useCallback(
    (id: number) => {
      // 清理 blob URL
      if (thumbUrls[id]) {
        URL.revokeObjectURL(thumbUrls[id]);
        setThumbUrls((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
      onChange(attachments.filter((a) => a.id !== id));
    },
    [attachments, onChange, thumbUrls],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Paperclip className="h-4 w-4 text-gray-400" />
        <span className="text-sm font-medium text-gray-700">
          {t("attachment.label")} ({attachments.length}/{MAX_ATTACHMENTS})
        </span>
      </div>

      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {attachments.map((att) => (
            <div key={att.id} className="group relative">
              {isImageContentType(att.content_type) && thumbUrls[att.id] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={thumbUrls[att.id]}
                  alt={att.original_filename}
                  className="h-20 w-20 cursor-pointer rounded-lg border border-gray-200 object-cover transition-shadow hover:shadow-md"
                  onClick={() => setLightboxId(att.id)}
                />
              ) : (
                <div className="flex h-20 w-20 flex-col items-center justify-center rounded-lg border border-gray-200 bg-gray-50">
                  <FileText className="h-6 w-6 text-gray-400" />
                  <span className="mt-1 w-full truncate px-1 text-center text-[10px] text-gray-400">
                    {att.original_filename.length > 12
                      ? att.original_filename.slice(-12)
                      : att.original_filename}
                  </span>
                  <span className="text-[9px] text-gray-300">
                    {formatFileSize(att.size_bytes)}
                  </span>
                </div>
              )}
              <button
                type="button"
                onClick={() => handleRemove(att.id)}
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
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed py-4 text-sm transition-colors ${
            dragOver
              ? "border-[#00505a]/60 bg-[#00505a]/5 text-gray-600"
              : "border-gray-200 text-gray-400 hover:border-[#00505a]/40 hover:text-gray-500"
          }`}
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

      {/* Lightbox 图片预览 */}
      {lightboxId !== null && thumbUrls[lightboxId] && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70"
          onClick={() => setLightboxId(null)}
        >
          <button
            type="button"
            onClick={() => setLightboxId(null)}
            className="absolute right-4 top-4 rounded-full bg-white/20 p-2 text-white transition-colors hover:bg-white/40"
          >
            <X className="h-5 w-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={thumbUrls[lightboxId]}
            alt={attachments.find((a) => a.id === lightboxId)?.original_filename ?? ""}
            className="max-h-[85vh] max-w-[90vw] rounded-lg object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
