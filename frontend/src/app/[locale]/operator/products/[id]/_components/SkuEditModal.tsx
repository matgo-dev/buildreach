"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { X, Plus, Trash2 } from "lucide-react";
import Toggle from "@/components/ui/Toggle";
import { AttrTemplate, ProductAttrInput, PriceTierInput } from "@/lib/api/operatorProducts";

export interface SkuFormData {
  sku_code?: string | null;
  manufacturer_model?: string | null;
  name?: string | null;
  color?: string | null;
  material?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  moq: number;
  lead_time_min?: number | null;
  lead_time_max?: number | null;
  packing_quantity?: number | null;
  gross_weight_kg?: number | null;
  volume_cbm?: number | null;
  can_consolidate: boolean;
  cargo_type?: string | null;
  is_default: boolean;
  status: string;
  price_tiers: PriceTierInput[];
  attributes: ProductAttrInput[];
  imageFiles: File[];
  existingImages: { id: number; url: string }[];
  removedImageIds: number[];
}

interface SkuEditModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (data: SkuFormData) => void;
  initial?: SkuFormData | null;
  isNew?: boolean;
  skuTemplates: AttrTemplate[];
  currency: string;
}


function emptySkuForm(): SkuFormData {
  return { sku_code: null, manufacturer_model: null, name: null, color: null, material: null, price_min: null, price_max: null, moq: 100, lead_time_min: null, lead_time_max: null, packing_quantity: null, gross_weight_kg: null, volume_cbm: null, can_consolidate: true, cargo_type: null, is_default: false, status: "ACTIVE", price_tiers: [], attributes: [], imageFiles: [], existingImages: [], removedImageIds: [] };
}

export default function SkuEditModal({ open, onClose, onConfirm, initial, isNew, skuTemplates, currency }: SkuEditModalProps) {
  const t = useTranslations("productDetail");
  const [form, setForm] = useState<SkuFormData>(initial || emptySkuForm());

  useEffect(() => {
    if (open) setForm(initial || emptySkuForm());
  }, [open, initial]);

  const skuFileRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const set = <K extends keyof SkuFormData>(key: K, val: SkuFormData[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: val };
      // MOQ 变化时同步首档 min_qty
      if (key === "moq" && next.price_tiers.length > 0) {
        next.price_tiers = next.price_tiers.map((t, i) =>
          i === 0 ? { ...t, min_qty: Number(val) || 1 } : t
        );
      }
      return next;
    });
  };

  const addTier = () => {
    const last = form.price_tiers[form.price_tiers.length - 1];
    const minQty = form.price_tiers.length === 0
      ? (form.moq || 1)
      : (last.max_qty || last.min_qty) + 1;
    set("price_tiers", [...form.price_tiers, { min_qty: minQty, max_qty: null, unit_price: 0, currency: currency }]);
  };
  const removeTier = (idx: number) => set("price_tiers", form.price_tiers.filter((_, i) => i !== idx));
  const updateTier = (idx: number, patch: Partial<PriceTierInput>) => {
    // 首档 min_qty 锁定为 MOQ
    if (idx === 0 && "min_qty" in patch) delete patch.min_qty;
    set("price_tiers", form.price_tiers.map((t, i) => i === idx ? { ...t, ...patch } : t));
  };

  const setAttr = (key: string, value: string) => {
    const exists = form.attributes.find((a) => a.attr_key === key);
    if (exists) set("attributes", form.attributes.map((a) => a.attr_key === key ? { ...a, attr_value: value } : a));
    else set("attributes", [...form.attributes, { attr_key: key, attr_value: value }]);
  };

  // SKU 图片 handlers are below (ref declared before early return)
  const handleSkuImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const valid = files.filter((f) => f.size <= 5 * 1024 * 1024 && ["image/jpeg", "image/png", "image/webp"].includes(f.type));
    if (valid.length > 0) set("imageFiles", [...form.imageFiles, ...valid]);
    if (skuFileRef.current) skuFileRef.current.value = "";
  };
  const removeNewImage = (idx: number) => set("imageFiles", form.imageFiles.filter((_, i) => i !== idx));
  const removeExistingImage = (imgId: number) => {
    set("existingImages", form.existingImages.filter((img) => img.id !== imgId));
    set("removedImageIds", [...form.removedImageIds, imgId]);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 overflow-y-auto py-8">
      <div className="w-full max-w-2xl bg-white rounded-xl shadow-2xl mx-4 my-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h3 className="text-base font-semibold text-slate-900">{isNew ? t("addSku") : t("editSku")}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
        </div>
        <div className="px-6 py-5 max-h-[70vh] overflow-y-auto space-y-5">
          {/* 基础信息 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">{t("fieldSkuCode")}</label>
              <input type="text" value={form.sku_code || ""} onChange={(e) => set("sku_code", e.target.value || null)} disabled={!isNew} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs disabled:bg-slate-100 disabled:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" placeholder={t("skuCodePlaceholder")} />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">{t("fieldModel")}</label>
              <input type="text" value={form.manufacturer_model || ""} onChange={(e) => set("manufacturer_model", e.target.value || null)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">{t("fieldName")}</label>
              <input type="text" value={form.name || ""} onChange={(e) => set("name", e.target.value || null)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">{t("fieldColor")}</label>
              <input type="text" value={form.color || ""} onChange={(e) => set("color", e.target.value || null)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">{t("fieldMaterial")}</label>
              <input type="text" value={form.material || ""} onChange={(e) => set("material", e.target.value || null)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
            </div>
            <div className="flex items-center gap-3">
              <label className="text-xs text-slate-500">{t("default")}</label>
              <Toggle checked={form.is_default} onChange={() => set("is_default", !form.is_default)} size="md" />
            </div>
          </div>
          {/* 商务参数 */}
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("sectionCommercial")}</h4>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("fieldMoq")} <span className="text-red-500">*</span></label>
                <input type="number" value={form.moq || ""} onChange={(e) => set("moq", Number(e.target.value) || 0)} min={1} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("fieldPriceMin")} <span className="text-red-500">*</span></label>
                <input type="number" value={form.price_min ?? ""} onChange={(e) => set("price_min", e.target.value ? Number(e.target.value) : null)} min={0} step={0.01} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("fieldPriceMax")} <span className="text-red-500">*</span></label>
                <input type="number" value={form.price_max ?? ""} onChange={(e) => set("price_max", e.target.value ? Number(e.target.value) : null)} min={0} step={0.01} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
            </div>
          </div>
          {/* 物流参数 */}
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("logistics")}</h4>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("fieldLeadTimeMin")}</label>
                <input type="number" value={form.lead_time_min ?? ""} onChange={(e) => set("lead_time_min", e.target.value ? Number(e.target.value) : null)} min={0} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("fieldLeadTimeMax")}</label>
                <input type="number" value={form.lead_time_max ?? ""} onChange={(e) => set("lead_time_max", e.target.value ? Number(e.target.value) : null)} min={0} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("packingQty")}</label>
                <input type="number" value={form.packing_quantity ?? ""} onChange={(e) => set("packing_quantity", e.target.value ? Number(e.target.value) : null)} min={1} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("grossWeight")} (kg)</label>
                <input type="number" value={form.gross_weight_kg ?? ""} onChange={(e) => set("gross_weight_kg", e.target.value ? Number(e.target.value) : null)} min={0} step={0.01} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("volume")} (cbm)</label>
                <input type="number" value={form.volume_cbm ?? ""} onChange={(e) => set("volume_cbm", e.target.value ? Number(e.target.value) : null)} min={0} step={0.001} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
              <div className="flex items-end gap-3 pb-1">
                <label className="text-xs text-slate-500">{t("canConsolidate")}</label>
                <Toggle checked={form.can_consolidate} onChange={() => set("can_consolidate", !form.can_consolidate)} size="md" />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t("cargoType")}</label>
                <input type="text" value={form.cargo_type || ""} onChange={(e) => set("cargo_type", e.target.value || null)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
              </div>
            </div>
          </div>
          {/* 阶梯价 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-slate-700">{t("priceTiers")}</h4>
              <button type="button" onClick={addTier} className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-0.5">
                <Plus className="h-3 w-3" /> {t("addTier")}
              </button>
            </div>
            {form.price_tiers.length > 0 && (
              <div className="space-y-2">
                {form.price_tiers.map((tier, i) => (
                  <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end">
                    <div>
                      <label className="text-[10px] text-slate-400">{t("tierMinQty")}{i === 0 && <span className="text-slate-300 ml-1">({t("tierEqualsModq")})</span>}</label>
                      <input type="number" value={i === 0 ? (form.moq || 1) : tier.min_qty} readOnly={i === 0} onChange={(e) => updateTier(i, { min_qty: Number(e.target.value) || 0 })} className={`w-full h-7 px-2 rounded border border-slate-200 text-xs ${i === 0 ? "bg-slate-100 text-slate-500 cursor-not-allowed" : ""}`} min={1} />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400">{t("tierMaxQty")}</label>
                      <input type="number" value={tier.max_qty ?? ""} onChange={(e) => updateTier(i, { max_qty: e.target.value ? Number(e.target.value) : null })} className="w-full h-7 px-2 rounded border border-slate-200 text-xs" placeholder="∞" />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400">{t("tierUnitPrice")}</label>
                      <input type="number" value={tier.unit_price || ""} onChange={(e) => updateTier(i, { unit_price: Number(e.target.value) || 0 })} className="w-full h-7 px-2 rounded border border-slate-200 text-xs" min={0} step={0.01} />
                    </div>
                    <button type="button" onClick={() => removeTier(i)} className="h-7 w-7 flex items-center justify-center text-red-400 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* SKU 属性 */}
          {skuTemplates.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("skuAttributes")}</h4>
              <div className="grid grid-cols-2 gap-3">
                {skuTemplates.map((tmpl) => {
                  const val = form.attributes.find((a) => a.attr_key === tmpl.attr_key)?.attr_value || "";
                  return (
                    <div key={tmpl.attr_key}>
                      <label className="text-xs text-slate-500 mb-1 block">
                        {tmpl.display_name}
                        {tmpl.attr_unit && <span className="text-slate-400 ml-1">({tmpl.attr_unit})</span>}
                        {tmpl.is_required && <span className="text-red-500 ml-0.5">*</span>}
                      </label>
                      {tmpl.attr_type === "select" && Array.isArray(tmpl.options) ? (
                        <select value={val} onChange={(e) => setAttr(tmpl.attr_key, e.target.value)} className="w-full h-8 px-2 rounded-lg border border-slate-200 text-xs focus:border-blue-500 outline-none">
                          <option value="">—</option>
                          {(tmpl.options as string[]).map((opt) => (<option key={opt} value={opt}>{opt}</option>))}
                        </select>
                      ) : (
                        <input type={tmpl.attr_type === "number" ? "number" : "text"} value={val} onChange={(e) => setAttr(tmpl.attr_key, e.target.value)} className="w-full h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none" />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {/* SKU 图片 */}
          <div>
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("skuImagesLabel")} <span className="text-slate-400 font-normal">({t("skuImagesMax")})</span></h4>
            <div className="flex flex-wrap gap-2">
              {form.existingImages.map((img) => (
                <div key={img.id} className="relative w-[72px] h-[72px] rounded-md border border-slate-200 overflow-hidden group">
                  <img src={img.url} alt="" className="w-full h-full object-cover" />
                  <button type="button" onClick={() => removeExistingImage(img.id)} className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white opacity-0 group-hover:opacity-100">×</button>
                </div>
              ))}
              {form.imageFiles.map((file, i) => (
                <div key={`new-${i}`} className="relative w-[72px] h-[72px] rounded-md border border-dashed border-blue-300 overflow-hidden group">
                  <img src={URL.createObjectURL(file)} alt="" className="w-full h-full object-cover" />
                  <span className="absolute top-0 left-0 bg-blue-400 text-white text-[8px] px-1 rounded-br">{t("newLabel")}</span>
                  <button type="button" onClick={() => removeNewImage(i)} className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white opacity-0 group-hover:opacity-100">×</button>
                </div>
              ))}
              {(form.existingImages.length + form.imageFiles.length) < 5 && (
                <button type="button" onClick={() => skuFileRef.current?.click()} className="flex w-[72px] h-[72px] flex-col items-center justify-center rounded-md border border-dashed border-slate-300 hover:border-blue-400">
                  <span className="text-lg text-slate-400">+</span>
                  <span className="text-[9px] text-slate-400">{t("upload")}</span>
                </button>
              )}
            </div>
            <input ref={skuFileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={handleSkuImageSelect} />
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-200">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">{t("cancel")}</button>
          <button type="button" onClick={() => onConfirm(form)} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">{t("confirm")}</button>
        </div>
      </div>
    </div>
  );
}
