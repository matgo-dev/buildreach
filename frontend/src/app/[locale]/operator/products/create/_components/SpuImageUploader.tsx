"use client";

import { useCallback, useRef } from "react";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
  t: (key: string) => string;
}

export function SpuImageUploader({ files, onChange, t }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files;
      if (!selected) return;
      const total = files.length + selected.length;
      // 最多 8 张
      const allowed = total <= 8 ? Array.from(selected) : Array.from(selected).slice(0, 8 - files.length);
      onChange([...files, ...allowed]);
      // 清空 input 以支持重复选同一文件
      e.target.value = "";
    },
    [files, onChange]
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

        {files.length < 8 && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex h-[100px] w-[100px] flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 hover:border-blue-400"
          >
            <span className="text-2xl text-slate-400">+</span>
            <span className="mt-0.5 text-[10px] text-slate-400">{t("images_upload")}</span>
          </button>
        )}
      </div>

      <p className="mt-2 text-[11px] text-slate-400">{t("images_drag_hint")}</p>

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
