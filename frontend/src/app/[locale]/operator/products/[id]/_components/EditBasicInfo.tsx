"use client";

import { useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Plus, X } from "lucide-react";
import Toggle from "@/components/ui/Toggle";
import type { ProductOperatorDetail, ProductUpdateInput } from "@/lib/api/operatorProducts";

interface EditBasicInfoProps {
  product: ProductOperatorDetail;
  value: ProductUpdateInput;
  onChange: (val: ProductUpdateInput) => void;
}

export default function EditBasicInfo({ product, value, onChange }: EditBasicInfoProps) {
  const t = useTranslations("productDetail");
  const locale = useLocale();
  const [certInput, setCertInput] = useState("");
  const certs = (value.certifications || []) as string[];

  const addCert = () => {
    const trimmed = certInput.trim();
    if (trimmed && !certs.includes(trimmed)) {
      onChange({ ...value, certifications: [...certs, trimmed] });
    }
    setCertInput("");
  };

  const removeCert = (idx: number) => {
    onChange({ ...value, certifications: certs.filter((_, i) => i !== idx) });
  };

  return (
    <section className="bg-white rounded-lg shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">{t("basicInfo")}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
        {/* SPU 编码 - 只读 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("spuCode")}</label>
          <div className="h-9 px-3 flex items-center rounded-lg bg-slate-100 text-sm text-slate-600 font-mono">
            {product.spu_code}
          </div>
        </div>
        {/* 品类 - 只读 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("category")}</label>
          <div className="h-9 px-3 flex items-center rounded-lg bg-slate-100 text-sm text-slate-600">
            {product.category_code}
          </div>
        </div>
        {/* 商品名 */}
        <div className="sm:col-span-2">
          <label className="text-xs text-slate-500 mb-1 block">
            {locale === "en" ? "Product Name (EN)" : "商品名称 (中文)"} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={value.name || ""}
            onChange={(e) => onChange({ ...value, name: e.target.value })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
            maxLength={200}
          />
        </div>
        {/* 品牌 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("brand")}</label>
          <input
            type="text"
            value={value.brand || ""}
            onChange={(e) => onChange({ ...value, brand: e.target.value || null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        {/* 产地 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("origin")}</label>
          <input
            type="text"
            value={value.origin || ""}
            onChange={(e) => onChange({ ...value, origin: e.target.value || null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        {/* HS Code */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("hsCode")}</label>
          <input
            type="text"
            value={value.hs_code || ""}
            onChange={(e) => onChange({ ...value, hs_code: e.target.value || null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        {/* 是否精选 */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500">{t("isFeatured")}</label>
          <Toggle checked={!!value.is_featured} onChange={() => onChange({ ...value, is_featured: !value.is_featured })} size="md" />
        </div>
        {/* 履约模式 */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500">{t("supplyMode")}</label>
          <div className="flex gap-3">
            <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
              <input
                type="radio"
                name="supply_mode"
                value="SUPPLIER_DIRECT"
                checked={value.supply_mode !== "PLATFORM_STOCK"}
                onChange={() => onChange({ ...value, supply_mode: "SUPPLIER_DIRECT" })}
                className="h-3.5 w-3.5 text-blue-600"
              />
              {t("supplyModeSupplierDirect")}
            </label>
            <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
              <input
                type="radio"
                name="supply_mode"
                value="PLATFORM_STOCK"
                checked={value.supply_mode === "PLATFORM_STOCK"}
                onChange={() => onChange({ ...value, supply_mode: "PLATFORM_STOCK" })}
                className="h-3.5 w-3.5 text-blue-600"
              />
              {t("supplyModePlatformStock")}
            </label>
          </div>
        </div>
        {/* 认证 */}
        <div className="sm:col-span-2">
          <label className="text-xs text-slate-500 mb-1 block">{t("certifications")}</label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {certs.map((c, i) => (
              <span key={i} className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded text-xs font-medium">
                {c}
                <button type="button" onClick={() => removeCert(i)} className="hover:text-emerald-900"><X className="h-3 w-3" /></button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={certInput}
              onChange={(e) => setCertInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCert(); } }}
              placeholder={locale === "en" ? "Add certification, press Enter" : "输入认证名,按回车添加"}
              className="flex-1 h-8 px-3 rounded-lg border border-slate-200 text-xs focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
            />
            <button type="button" onClick={addCert} className="h-8 px-2.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50">
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        {/* 卖点 */}
        <div className="sm:col-span-2">
          <label className="text-xs text-slate-500 mb-1 block">{t("sellingPoints")}</label>
          <input
            type="text"
            value={value.selling_points || ""}
            onChange={(e) => onChange({ ...value, selling_points: e.target.value || null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        {/* 描述 */}
        <div className="sm:col-span-2">
          <label className="text-xs text-slate-500 mb-1 block">{t("description")}</label>
          <textarea
            value={value.description || ""}
            onChange={(e) => onChange({ ...value, description: e.target.value || null })}
            rows={4}
            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none resize-y"
          />
        </div>

        {/* ── 物流参数 ── */}
        <div className="sm:col-span-2 mt-2 mb-1">
          <h4 className="text-xs font-semibold text-slate-600 border-b border-slate-100 pb-1.5">
            {t("logisticsTitle")}
          </h4>
        </div>
        {/* 交期 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("leadTimeMin")}</label>
          <input
            type="number" min="0"
            value={value.lead_time_min ?? ""}
            onChange={(e) => onChange({ ...value, lead_time_min: e.target.value ? Number(e.target.value) : null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("leadTimeMax")}</label>
          <input
            type="number" min="0"
            value={value.lead_time_max ?? ""}
            onChange={(e) => onChange({ ...value, lead_time_max: e.target.value ? Number(e.target.value) : null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        {/* 装量 / 毛重 / 体积 */}
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("packingQuantity")}</label>
          <input
            type="number" min="1"
            value={value.packing_quantity ?? ""}
            onChange={(e) => onChange({ ...value, packing_quantity: e.target.value ? Number(e.target.value) : null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("grossWeightKg")}</label>
          <input
            type="number" min="0" step="0.01"
            value={value.gross_weight_kg ?? ""}
            onChange={(e) => onChange({ ...value, gross_weight_kg: e.target.value ? Number(e.target.value) : null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
            placeholder="kg"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("volumeCbm")}</label>
          <input
            type="number" min="0" step="0.0001"
            value={value.volume_cbm ?? ""}
            onChange={(e) => onChange({ ...value, volume_cbm: e.target.value ? Number(e.target.value) : null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
            placeholder="CBM"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">{t("cargoType")}</label>
          <input
            type="text" maxLength={20}
            value={value.cargo_type || ""}
            onChange={(e) => onChange({ ...value, cargo_type: e.target.value || null })}
            className="w-full h-9 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
          />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500">{t("canConsolidate")}</label>
          <Toggle checked={value.can_consolidate ?? true} onChange={() => onChange({ ...value, can_consolidate: !(value.can_consolidate ?? true) })} size="md" />
        </div>
      </div>
    </section>
  );
}
