"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, X, Star } from "lucide-react";
import { ProductImage } from "@/lib/api/operatorProducts";
import { useToast } from "@/components/ui/Toast";

export interface ImageChange {
  added: File[];
  removed: number[];
  newMainId: number | null;
  newOrder: number[] | null;
}

interface EditImagesProps {
  images: ProductImage[];
  imageChange: ImageChange;
  onChange: (change: ImageChange) => void;
  previews: string[];
}

const MAX_IMAGES = 8;
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const MIN_DIMENSION = 200;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

function readImageDimension(file: File): Promise<{ w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("cannot read image")); };
    img.src = url;
  });
}

export default function EditImages({ images, imageChange, onChange, previews }: EditImagesProps) {
  const t = useTranslations("productDetail");
  const { warning: toastWarning } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [dragStartIdx, setDragStartIdx] = useState<number | null>(null);
  const [validating, setValidating] = useState(false);

  const visibleImages = images.filter((img) => !imageChange.removed.includes(img.id));
  const totalCount = visibleImages.length + imageChange.added.length;
  const canAdd = totalCount < MAX_IMAGES;
  const currentMainId = imageChange.newMainId || images.find((img) => img.image_type === "MAIN")?.id || null;

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (fileRef.current) fileRef.current.value = "";

    setValidating(true);
    const valid: File[] = [];
    for (const file of files) {
      if (totalCount + valid.length >= MAX_IMAGES) break;
      if (!ACCEPTED_TYPES.includes(file.type)) {
        toastWarning(t("imageRejectFormat"));
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        toastWarning(t("imageRejectSize"));
        continue;
      }
      try {
        const { w, h } = await readImageDimension(file);
        if (w < MIN_DIMENSION || h < MIN_DIMENSION) {
          toastWarning(t("imageRejectDimension", { w, h }));
          continue;
        }
      } catch {
        toastWarning(t("imageRejectFormat"));
        continue;
      }
      valid.push(file);
    }
    setValidating(false);
    if (valid.length > 0) {
      onChange({ ...imageChange, added: [...imageChange.added, ...valid] });
    }
  }, [totalCount, imageChange, onChange, t, toastWarning]);

  const removeExisting = (id: number) => {
    onChange({ ...imageChange, removed: [...imageChange.removed, id], newMainId: currentMainId === id ? null : imageChange.newMainId });
  };

  const removeAdded = (idx: number) => {
    onChange({ ...imageChange, added: imageChange.added.filter((_, i) => i !== idx) });
  };

  const setMain = (id: number) => {
    onChange({ ...imageChange, newMainId: id });
  };

  const handleDragStart = (idx: number) => setDragStartIdx(idx);
  const handleDragOver = (e: React.DragEvent, idx: number) => { e.preventDefault(); setDragOverIdx(idx); };
  const handleDrop = (dropIdx: number) => {
    if (dragStartIdx === null || dragStartIdx === dropIdx) { setDragOverIdx(null); setDragStartIdx(null); return; }
    const ids = visibleImages.map((img) => img.id);
    const [moved] = ids.splice(dragStartIdx, 1);
    ids.splice(dropIdx, 0, moved);
    onChange({ ...imageChange, newOrder: ids });
    setDragOverIdx(null);
    setDragStartIdx(null);
  };

  return (
    <section className="bg-white rounded-lg shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">
        {t("productImages")} <span className="text-slate-400 font-normal">({totalCount}/8)</span>
      </h3>
      <div className="flex flex-wrap gap-3">
        {visibleImages.map((img, idx) => (
          <div
            key={img.id}
            draggable
            onDragStart={() => handleDragStart(idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDrop={() => handleDrop(idx)}
            onDragEnd={() => { setDragOverIdx(null); setDragStartIdx(null); }}
            className={`relative w-24 h-24 rounded-lg overflow-hidden border-2 group cursor-move ${currentMainId === img.id ? "border-blue-500" : "border-slate-200"} ${dragOverIdx === idx ? "ring-2 ring-blue-300" : ""} bg-slate-100`}
          >
            <img src={img.full_url} alt="" className="w-full h-full object-cover" />
            {currentMainId === img.id && (
              <span className="absolute top-0 left-0 bg-blue-500 text-white text-[9px] px-1.5 py-0.5 rounded-br">{t("mainImage")}</span>
            )}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              {currentMainId !== img.id && (
                <button type="button" onClick={() => setMain(img.id)} className="w-7 h-7 rounded-full bg-white/90 flex items-center justify-center text-amber-500 hover:bg-white" title={t("setAsMain")}>
                  <Star className="h-3.5 w-3.5" />
                </button>
              )}
              <button type="button" onClick={() => removeExisting(img.id)} className="w-7 h-7 rounded-full bg-white/90 flex items-center justify-center text-red-500 hover:bg-white" title={t("deleteImage")}>
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
        {previews.map((url, idx) => (
          <div key={`new-${idx}`} className="relative w-24 h-24 rounded-lg overflow-hidden border-2 border-dashed border-blue-300 bg-blue-50 group">
            <img src={url} alt="" className="w-full h-full object-cover" />
            <span className="absolute top-0 left-0 bg-blue-400 text-white text-[9px] px-1.5 py-0.5 rounded-br">NEW</span>
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <button type="button" onClick={() => removeAdded(idx)} className="w-7 h-7 rounded-full bg-white/90 flex items-center justify-center text-red-500 hover:bg-white">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
        {canAdd && (
          <button type="button" onClick={() => fileRef.current?.click()} disabled={validating} className="w-24 h-24 rounded-lg border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 hover:border-blue-400 hover:text-blue-500 transition-colors disabled:opacity-50">
            <Plus className="h-5 w-5" />
            <span className="text-[10px] mt-1">{validating ? "..." : t("uploadImage")}</span>
          </button>
        )}
      </div>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handleFileSelect} className="hidden" />
      <p className="mt-2 text-[11px] text-slate-400">
        {t("imageRequirements")}
      </p>
    </section>
  );
}
