"use client";

import { useCallback, useRef, useState } from "react";
import { useToast } from "@/components/ui/Toast";

const MAX_IMAGES = 8;
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const MIN_DIMENSION = 200;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

/** 读取图片宽高 */
function readImageDimension(file: File): Promise<{ w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("cannot read image")); };
    img.src = url;
  });
}

export function SpuImageUploader({ files, onChange, t }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { warning: toastWarning } = useToast();
  const [validating, setValidating] = useState(false);

  const handleSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files;
      if (!selected) return;
      if (inputRef.current) inputRef.current.value = "";

      setValidating(true);
      const accepted: File[] = [];
      for (const file of Array.from(selected)) {
        if (files.length + accepted.length >= MAX_IMAGES) break;

        // 格式校验
        if (!ACCEPTED_TYPES.includes(file.type)) {
          toastWarning(t("images_reject_format"));
          continue;
        }
        // 大小校验
        if (file.size > MAX_FILE_SIZE) {
          toastWarning(t("images_reject_size"));
          continue;
        }
        // 尺寸校验
        try {
          const { w, h } = await readImageDimension(file);
          if (w < MIN_DIMENSION || h < MIN_DIMENSION) {
            toastWarning(t("images_reject_dimension", { w, h }));
            continue;
          }
        } catch {
          toastWarning(t("images_reject_format"));
          continue;
        }
        accepted.push(file);
      }
      setValidating(false);
      if (accepted.length > 0) {
        onChange([...files, ...accepted]);
      }
    },
    [files, onChange, t, toastWarning]
  );

  const remove = useCallback(
    (idx: number) => {
      onChange(files.filter((_, i) => i !== idx));
    },
    [files, onChange]
  );

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap gap-3">
        {files.map((file, i) => (
          <div
            key={i}
            className={`relative h-[100px] w-[100px] overflow-hidden rounded-lg ${
              i === 0 ? "border-2 border-blue-500" : "border border-blue-200"
            } bg-blue-50`}
          >
            <img
              src={URL.createObjectURL(file)}
              alt=""
              className="h-full w-full object-cover"
            />
            <span className="absolute bottom-0 left-0 right-0 bg-black/30 text-center text-[10px] text-white">
              {i === 0 ? t("images_main") : t("images_gallery")}
            </span>
            <button
              type="button"
              onClick={() => remove(i)}
              className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white shadow"
            >
              ×
            </button>
          </div>
        ))}

        {files.length < MAX_IMAGES && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={validating}
            className="flex h-[100px] w-[100px] flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 hover:border-blue-400 disabled:opacity-50"
          >
            <span className="text-2xl text-slate-400">{validating ? "..." : "+"}</span>
            <span className="mt-0.5 text-[10px] text-slate-400">{t("images_upload")}</span>
          </button>
        )}
      </div>

      <p className="mt-2 text-[11px] text-slate-400">
        {t("images_requirements")} · {t("images_drag_hint")}
      </p>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="hidden"
        onChange={handleSelect}
      />
    </div>
  );
}
