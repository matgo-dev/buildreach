"use client";

import { useCallback, useRef } from "react";
import type { AttrTemplate } from "@/lib/api/operatorProducts";
import { SKU_UNITS, type SkuUnitCode } from "@/lib/api/operatorProducts";
import type { SkuFormState } from "./ProductCreatePage";

interface Props {
  sku: SkuFormState;
  index: number;
  templates: AttrTemplate[];
  onUpdate: (patch: Partial<SkuFormState>) => void;
  onRemove: () => void;
  onSetDefault: () => void;
  onOpenTiers: () => void;
  error: string | null;
  t: (key: string) => string;
  tUnit: (key: string) => string;
}

const INPUT_CLS =
  "h-8 w-full rounded border border-slate-200 px-2 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/20";
const SELECT_CLS =
  "h-8 w-full rounded border border-slate-200 bg-white px-2 text-xs focus:border-blue-500 focus:outline-none";
const LABEL_CLS = "text-xs text-slate-500";

export function SkuCard({ sku, index, templates, onUpdate, onRemove, onSetDefault, onOpenTiers, error, t, tUnit }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const set = useCallback(
    <K extends keyof SkuFormState>(key: K, value: SkuFormState[K]) => {
      onUpdate({ [key]: value } as Partial<SkuFormState>);
    },
    [onUpdate]
  );

  const setAttr = useCallback(
    (attrKey: string, value: string) => {
      onUpdate({ attributes: { ...sku.attributes, [attrKey]: value } });
    },
    [onUpdate, sku.attributes]
  );

  const handleImageSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) {
        onUpdate({ imageFiles: [...sku.imageFiles, ...Array.from(files)] });
      }
    },
    [onUpdate, sku.imageFiles]
  );

  const removeImage = useCallback(
    (idx: number) => {
      onUpdate({ imageFiles: sku.imageFiles.filter((_, i) => i !== idx) });
    },
    [onUpdate, sku.imageFiles]
  );

  const isDefault = sku.is_default;
  const hasError = !!error;
  const borderCls = hasError
    ? "border-2 border-red-500"
    : isDefault
      ? "border-2 border-blue-500"
      : "border border-slate-200";
  const headerBg = hasError ? "bg-red-50" : isDefault ? "bg-blue-50" : "bg-slate-50";

  return (
    <div className={`mb-4 overflow-hidden rounded-xl ${borderCls}`}>
      {/* 错误提示 */}
      {hasError && (
        <div className="flex items-center gap-2 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          <span className="font-medium">⚠</span>
          <span>{error}</span>
        </div>
      )}
      {/* 卡片头 */}
      <div className={`flex items-center justify-between px-4 py-3 ${headerBg}`}>
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-semibold text-slate-800">{t("sku_title")} #{index + 1}</span>
          {isDefault && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] text-blue-800">
              {t("sku_default")}
            </span>
          )}
          <span className="text-[11px] text-slate-400">{t("sku_code_auto")}</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1 text-xs text-slate-500">
            <input
              type="radio"
              name="defaultSku"
              checked={isDefault}
              onChange={onSetDefault}
            />
            {t("sku_set_default")}
          </label>
          <button type="button" onClick={onRemove} className="text-xs text-red-500 hover:text-red-700">
            {t("sku_delete")}
          </button>
        </div>
      </div>

      <div className="p-4">
        {/* 商务参数 */}
        <h4 className="mb-2.5 border-b border-slate-100 pb-1.5 text-[13px] font-medium text-slate-600">
          {t("sku_section_commercial")}
        </h4>
        <div className="mb-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {/* 计量单位 */}
          <div>
            <label className={LABEL_CLS}>
              {t("field_unit")} <span className="text-red-500">*</span>
            </label>
            <select
              className={SELECT_CLS}
              value={sku.unit}
              onChange={(e) => set("unit", e.target.value as SkuUnitCode)}
            >
              {SKU_UNITS.map((u) => (
                <option key={u} value={u}>
                  {u} - {tUnit(u)}
                </option>
              ))}
            </select>
          </div>

          {/* MOQ */}
          <div>
            <label className={LABEL_CLS}>
              {t("field_moq")} <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              className={INPUT_CLS}
              value={sku.moq}
              onChange={(e) => set("moq", e.target.value)}
            />
          </div>

          {/* 最低价 */}
          <div>
            <label className={LABEL_CLS}>{t("field_price_min")} ({sku.currency})</label>
            <input
              type="number"
              min="0"
              step="0.01"
              className={INPUT_CLS}
              value={sku.price_min}
              onChange={(e) => set("price_min", e.target.value)}
            />
          </div>

          {/* 最高价 */}
          <div>
            <label className={LABEL_CLS}>{t("field_price_max")} ({sku.currency})</label>
            <input
              type="number"
              min="0"
              step="0.01"
              className={INPUT_CLS}
              value={sku.price_max}
              onChange={(e) => set("price_max", e.target.value)}
            />
          </div>

          {/* 币种 */}
          <div>
            <label className={LABEL_CLS}>{t("field_currency")}</label>
            <select
              className={SELECT_CLS}
              value={sku.currency}
              onChange={(e) => set("currency", e.target.value)}
            >
              <option value="TZS">TZS</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
            </select>
          </div>

          {/* 交期 */}
          <div>
            <label className={LABEL_CLS}>{t("field_lead_time")}</label>
            <div className="mt-1 flex items-center gap-1">
              <input
                type="number"
                min="0"
                className={INPUT_CLS}
                value={sku.lead_time_min}
                onChange={(e) => set("lead_time_min", e.target.value)}
              />
              <span className="text-slate-400">~</span>
              <input
                type="number"
                min="0"
                className={INPUT_CLS}
                value={sku.lead_time_max}
                onChange={(e) => set("lead_time_max", e.target.value)}
              />
            </div>
          </div>

          {/* 阶梯价入口 */}
          <div className="col-span-2 flex items-end">
            <button
              type="button"
              onClick={onOpenTiers}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              📊 {t("field_price_tiers")} →
            </button>
            <span className="ml-1 text-[10px] text-slate-400">({t("field_price_tiers_hint")})</span>
            {sku.price_tiers.length > 0 && (
              <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-700">
                {sku.price_tiers.length} {t("tier_title")}
              </span>
            )}
          </div>
        </div>

        {/* 品类属性 */}
        {templates.length > 0 && (
          <>
            <h4 className="mb-2.5 border-b border-slate-100 pb-1.5 text-[13px] font-medium text-slate-600">
              {t("sku_section_attrs")}
              <span className="ml-1.5 text-[10px] font-normal text-slate-400">
                {t("sku_section_attrs_hint")} · {templates.length}
              </span>
            </h4>
            <div className="mb-4 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              {templates.map((tpl) => (
                <div key={tpl.attr_key}>
                  <label className={LABEL_CLS}>
                    {tpl.display_name}
                    {tpl.is_required && <span className="text-red-500"> *</span>}
                    {tpl.attr_unit && <span className="text-slate-400"> ({tpl.attr_unit})</span>}
                  </label>
                  {tpl.attr_type === "select" && tpl.options ? (
                    <select
                      className={SELECT_CLS}
                      value={sku.attributes[tpl.attr_key] ?? ""}
                      onChange={(e) => setAttr(tpl.attr_key, e.target.value)}
                    >
                      <option value="">--</option>
                      {(Array.isArray(tpl.options) ? tpl.options : Object.keys(tpl.options)).map(
                        (opt: unknown) => (
                          <option key={String(opt)} value={String(opt)}>
                            {String(opt)}
                          </option>
                        )
                      )}
                    </select>
                  ) : (
                    <input
                      type={tpl.attr_type === "number" ? "number" : "text"}
                      className={INPUT_CLS}
                      value={sku.attributes[tpl.attr_key] ?? ""}
                      onChange={(e) => setAttr(tpl.attr_key, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* SKU 图片 */}
        <h4 className="mb-2.5 border-b border-slate-100 pb-1.5 text-[13px] font-medium text-slate-600">
          {t("sku_section_images")}
          <span className="ml-1.5 text-[10px] font-normal text-slate-400">{t("sku_section_images_hint")}</span>
        </h4>
        <div className="mb-4 flex flex-wrap gap-2">
          {sku.imageFiles.map((file, i) => (
            <div
              key={i}
              className="relative h-[72px] w-[72px] overflow-hidden rounded-md border border-slate-200"
            >
              <img
                src={URL.createObjectURL(file)}
                alt=""
                className="h-full w-full object-cover"
              />
              <button
                type="button"
                onClick={() => removeImage(i)}
                className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white"
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex h-[72px] w-[72px] flex-col items-center justify-center rounded-md border border-dashed border-slate-300 hover:border-blue-400"
          >
            <span className="text-lg text-slate-400">+</span>
            <span className="text-[9px] text-slate-400">{t("images_upload")}</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={handleImageSelect}
          />
        </div>

        {/* 物流参数折叠 */}
        <details>
          <summary className="cursor-pointer py-1.5 text-[13px] text-blue-600">
            ▶ {t("sku_section_logistics")}
          </summary>
          <div className="mt-2.5 grid grid-cols-2 gap-2.5 rounded-md bg-slate-50 p-3 sm:grid-cols-4">
            <div>
              <label className={LABEL_CLS}>{t("field_packing_quantity")}</label>
              <input
                type="number"
                min="1"
                className={INPUT_CLS}
                value={sku.packing_quantity}
                onChange={(e) => set("packing_quantity", e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>{t("field_gross_weight")}</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                className={INPUT_CLS}
                value={sku.gross_weight_kg}
                onChange={(e) => set("gross_weight_kg", e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>{t("field_volume")}</label>
              <input
                type="number"
                min="0.001"
                step="0.001"
                className={INPUT_CLS}
                value={sku.volume_cbm}
                onChange={(e) => set("volume_cbm", e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>{t("field_can_consolidate")}</label>
              <div className="mt-2">
                <button
                  type="button"
                  onClick={() => set("can_consolidate", !sku.can_consolidate)}
                  className={`relative h-[18px] w-9 rounded-full transition-colors ${sku.can_consolidate ? "bg-blue-500" : "bg-slate-300"}`}
                >
                  <div
                    className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${sku.can_consolidate ? "translate-x-[18px]" : "translate-x-0.5"}`}
                  />
                </button>
              </div>
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}
