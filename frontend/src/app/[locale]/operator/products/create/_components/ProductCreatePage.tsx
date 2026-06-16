"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { v4 as uuidv4 } from "uuid";

import { CategoryCascader, EMPTY_CATEGORY, type SelectedCategory } from "@/components/category/CategoryCascader";
import { operatorProductsApi, type AttrTemplate, type ProductAttrInput, type PriceTierInput, type AggregateSkuInput } from "@/lib/api/operatorProducts";
import { SKU_UNITS, type SkuUnitCode } from "@/lib/api/operatorProducts";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/Toast";
import { SectionAnchorNav } from "./SectionAnchorNav";
import { SkuCard } from "./SkuCard";
import { SpuImageUploader } from "./SpuImageUploader";
import { PriceTierModal } from "./PriceTierModal";

// ---------- SKU 表单状态 ----------

export interface SkuFormState {
  _clientId: string;                    // 前端临时 ID
  sku_code: string;
  manufacturer_model: string;
  name: string;
  color: string;
  material: string;
  price_min: string;
  price_max: string;
  moq: string;
  lead_time_min: string;
  lead_time_max: string;
  packing_quantity: string;
  gross_weight_kg: string;
  volume_cbm: string;
  can_consolidate: boolean;
  cargo_type: string;
  is_default: boolean;
  price_tiers: PriceTierInput[];
  attributes: Record<string, string>;   // attr_key → attr_value
  imageFiles: File[];                   // 待上传的 SKU 图片
}

function createEmptySku(isDefault: boolean): SkuFormState {
  return {
    _clientId: uuidv4(),
    sku_code: "",
    manufacturer_model: "",
    name: "",
    color: "",
    material: "",
    price_min: "",
    price_max: "",
    moq: "1",
    lead_time_min: "",
    lead_time_max: "",
    packing_quantity: "",
    gross_weight_kg: "",
    volume_cbm: "",
    can_consolidate: true,
    cargo_type: "",
    is_default: isDefault,
    price_tiers: [],
    attributes: {},
    imageFiles: [],
  };
}

// ---------- SPU 表单状态 ----------

interface SpuFormState {
  spu_code: string;
  name: string;
  description: string;
  origin: string;
  hs_code: string;
  brand: string;
  certifications: string[];
  selling_points: string;
  is_featured: boolean;
  supply_mode: string;
  unit: SkuUnitCode;
  currency: string;
  // 物流参数（SPU 级）
  lead_time_min: string;
  lead_time_max: string;
  packing_quantity: string;
  gross_weight_kg: string;
  volume_cbm: string;
  can_consolidate: boolean;
  cargo_type: string;
  spuAttributes: Record<string, string>;  // scope=SPU 属性
}

const INITIAL_SPU: SpuFormState = {
  spu_code: "",
  name: "",
  description: "",
  origin: "中国",
  hs_code: "",
  brand: "",
  certifications: [],
  selling_points: "",
  is_featured: false,
  supply_mode: "SUPPLIER_DIRECT",
  unit: "PCS",
  currency: "TZS",
  lead_time_min: "",
  lead_time_max: "",
  packing_quantity: "",
  gross_weight_kg: "",
  volume_cbm: "",
  can_consolidate: true,
  cargo_type: "",
  spuAttributes: {},
};

// ---------- sessionStorage 草稿持久化 ----------

const STORAGE_KEY = "product_create_draft";

interface DraftState {
  category: SelectedCategory;
  spu: SpuFormState;
  skus: SkuFormState[];
}

function saveDraft(category: SelectedCategory, spu: SpuFormState, skus: SkuFormState[]) {
  try {
    const cleanSkus = skus.map(({ imageFiles, ...rest }) => ({ ...rest, imageFiles: [] }));
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ category, spu, skus: cleanSkus }));
  } catch { /* 超出存储限制则静默失败 */ }
}

function loadDraft(): DraftState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as DraftState;
  } catch { return null; }
}

function clearDraft() {
  try { sessionStorage.removeItem(STORAGE_KEY); } catch {}
}

// ---------- 主组件 ----------

export function ProductCreatePage() {
  const router = useRouter();
  const t = useTranslations("productCreate");
  const tUnit = useTranslations("unit");
  const tError = useTranslations("error");
  const locale = useLocale();

  // 草稿恢复（不自动恢复，弹提示让用户选择）
  const [pendingDraft, setPendingDraft] = useState<DraftState | null>(() => loadDraft());
  const [draftRestored, setDraftRestored] = useState(false);

  // 品类选择
  const [category, setCategory] = useState<SelectedCategory>(EMPTY_CATEGORY);
  const isLeafSelected = !!category.level3Code;

  // 属性模板
  const [attrTemplates, setAttrTemplates] = useState<AttrTemplate[]>([]);
  const [attrLoading, setAttrLoading] = useState(false);
  const spuTemplates = attrTemplates.filter((t) => t.scope === "SPU");
  const skuTemplates = attrTemplates.filter((t) => t.scope === "SKU");

  // SPU 表单
  const [spu, setSpu] = useState<SpuFormState>(INITIAL_SPU);

  // SKU 列表（默认空，用户点"添加 SKU"才创建）
  const [skus, setSkus] = useState<SkuFormState[]>([]);

  // 恢复草稿
  const restoreDraft = useCallback(() => {
    if (!pendingDraft) return;
    setCategory(pendingDraft.category);
    setSpu(pendingDraft.spu);
    setSkus(pendingDraft.skus);
    setPendingDraft(null);
    setDraftRestored(true);
    // 拉属性模板
    if (pendingDraft.category.level3Code) {
      setAttrLoading(true);
      operatorProductsApi.getAttrTemplates(pendingDraft.category.level3Code)
        .then(setAttrTemplates)
        .catch(() => setAttrTemplates([]))
        .finally(() => setAttrLoading(false));
    }
  }, [pendingDraft]);

  const discardDraft = useCallback(() => {
    clearDraft();
    setPendingDraft(null);
  }, []);

  // SPU 图片（File 不可序列化，不缓存）
  const [spuImageFiles, setSpuImageFiles] = useState<File[]>([]);

  // 表单变更时自动保存草稿
  useEffect(() => {
    saveDraft(category, spu, skus);
  }, [category, spu, skus]);

  // 提交状态
  const [submitting, setSubmitting] = useState(false);
  // 部分成功时记录已创建的商品 ID，用于引导跳转
  const [createdProductId, setCreatedProductId] = useState<number | null>(null);
  // 出错的 SKU clientId，用于高亮卡片
  const [errorSkuId, setErrorSkuId] = useState<string | null>(null);
  const { success: toastSuccess, error: toastError, warning: toastWarning } = useToast();
  // 字段级错误，key 为字段标识，value 为 i18n 后的错误文案
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // 阶梯价弹窗
  const [tierModalSkuId, setTierModalSkuId] = useState<string | null>(null);

  // 认证标签输入
  const [certInput, setCertInput] = useState("");

  // 锚点 ref
  const sectionRefs = {
    basic: useRef<HTMLDivElement>(null),
    sku: useRef<HTMLDivElement>(null),
    images: useRef<HTMLDivElement>(null),
  };

  // 清除单个字段错误（用户编辑时调用）
  const clearFieldError = useCallback((key: string) => {
    setFieldErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  // ---------- 品类选择变更 → 拉属性模板 ----------
  const handleCategoryChange = useCallback(async (val: SelectedCategory) => {
    setCategory(val);
    clearFieldError("category");
    if (val.level3Code) {
      setAttrLoading(true);
      try {
        const templates = await operatorProductsApi.getAttrTemplates(val.level3Code);
        setAttrTemplates(templates);
      } catch {
        setAttrTemplates([]);
      } finally {
        setAttrLoading(false);
      }
    } else {
      setAttrTemplates([]);
    }
  }, [clearFieldError]);

  // ---------- SPU 字段更新 ----------
  const updateSpu = useCallback(<K extends keyof SpuFormState>(key: K, value: SpuFormState[K]) => {
    setSpu((prev) => ({ ...prev, [key]: value }));
    // 编辑 name 时清除对应字段错误
    if (key === "name") clearFieldError("name");
  }, [clearFieldError]);

  // ---------- 认证标签 ----------
  const addCertification = useCallback(() => {
    const val = certInput.trim();
    if (val && !spu.certifications.includes(val)) {
      updateSpu("certifications", [...spu.certifications, val]);
    }
    setCertInput("");
  }, [certInput, spu.certifications, updateSpu]);

  const removeCertification = useCallback((cert: string) => {
    updateSpu("certifications", spu.certifications.filter((c) => c !== cert));
  }, [spu.certifications, updateSpu]);

  // ---------- SKU 操作 ----------
  const addSku = useCallback(() => {
    setSkus((prev) => [...prev, createEmptySku(prev.length === 0)]);
    clearFieldError("skus");
  }, [clearFieldError]);

  const removeSku = useCallback((clientId: string) => {
    setSkus((prev) => {
      const next = prev.filter((s) => s._clientId !== clientId);
      // 如果删了默认 SKU，把第一个设为默认
      if (next.length > 0 && !next.some((s) => s.is_default)) {
        next[0] = { ...next[0], is_default: true };
      }
      return next;
    });
  }, []);

  const setDefaultSku = useCallback((clientId: string) => {
    setSkus((prev) => prev.map((s) => ({ ...s, is_default: s._clientId === clientId })));
  }, []);

  const updateSku = useCallback((clientId: string, patch: Partial<SkuFormState>) => {
    setSkus((prev) => prev.map((s) => (s._clientId === clientId ? { ...s, ...patch } : s)));
    // 编辑价格时清除对应 SKU 价格错误
    if ("price_min" in patch || "price_max" in patch) {
      clearFieldError(`sku_price_${clientId}`);
    }
  }, [clearFieldError]);

  // ---------- 错误信息提取（走 i18n） ----------
  const extractErrorMsg = useCallback((err: unknown): string => {
    // 网络错误（fetch 失败、断网等）→ 友好提示
    if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
      return t("error_network");
    }
    if (err instanceof ApiError && err.messageKey) {
      try {
        const keyPath = err.messageKey.startsWith("error.")
          ? err.messageKey.slice(6)
          : err.messageKey;
        return tError(keyPath);
      } catch {
        // i18n key 不存在，回退到 message
      }
    }
    if (err instanceof Error) return err.message;
    return String(err);
  }, [t, tError]);

  // ---------- 提交（建壳：SPU-only 或 SPU+SKU 聚合） ----------
  const handleSubmit = useCallback(async (publish: boolean) => {
    setErrorSkuId(null);

    // 如果 SPU 已创建（上次部分成功），跳过校验和创建，只做图片+上架
    const existingId = createdProductId;

    if (!existingId) {
      // 前端预校验 — 草稿仅需品类+名称；上架需完整校验
      const errors: Record<string, string> = {};
      if (!category.level3Code) errors.category = t("validate_category_required");
      if (!spu.name.trim()) errors.name = t("validate_name_required");
      // ADR-0006 方案 C：不强制 SKU，上架只需品类+名称+图片
      if (publish && spuImageFiles.length === 0) errors.images = t("validate_image_required");
      if (Object.keys(errors).length > 0) {
        setFieldErrors(errors);
        requestAnimationFrame(() => {
          document.querySelector("[data-field-error=\"true\"]")?.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        return;
      }
      setFieldErrors({});
    }

    setSubmitting(true);
    let productId: number | null = existingId;
    let skuMappings: { client_id: string | null; id: number; sku_code: string }[] | undefined;
    try {
      // 1) 建壳（仅首次，部分成功 retry 时跳过）
      if (!productId) {
        const spuAttrs: ProductAttrInput[] = Object.entries(spu.spuAttributes)
          .filter(([, v]) => v.trim())
          .map(([k, v]) => ({ attr_key: k, attr_value: v }));

        if (skus.length > 0) {
          // 有 SKU → 聚合创建（SPU + SKU）
          const aggregateSkus: AggregateSkuInput[] = skus.map((sku) => {
            const skuAttrs: ProductAttrInput[] = Object.entries(sku.attributes)
              .filter(([, v]) => v.trim())
              .map(([k, v]) => ({ attr_key: k, attr_value: v }));
            return {
              client_id: sku._clientId,
              manufacturer_model: sku.manufacturer_model || undefined,
              name: sku.name || undefined,
              color: sku.color || undefined,
              material: sku.material || undefined,
              price_min: sku.price_min ? Number(sku.price_min) : undefined,
              price_max: sku.price_max ? Number(sku.price_max) : undefined,
              moq: Number(sku.moq) || 1,
              lead_time_min: sku.lead_time_min ? Number(sku.lead_time_min) : undefined,
              lead_time_max: sku.lead_time_max ? Number(sku.lead_time_max) : undefined,
              packing_quantity: sku.packing_quantity ? Number(sku.packing_quantity) : undefined,
              gross_weight_kg: sku.gross_weight_kg ? Number(sku.gross_weight_kg) : undefined,
              volume_cbm: sku.volume_cbm ? Number(sku.volume_cbm) : undefined,
              can_consolidate: sku.can_consolidate,
              cargo_type: sku.cargo_type || undefined,
              is_default: sku.is_default,
              price_tiers: sku.price_tiers.length > 0 ? sku.price_tiers : undefined,
              attributes: skuAttrs.length > 0 ? skuAttrs : undefined,
            };
          });

          const result = await operatorProductsApi.createAggregate({
            category_code: category.level3Code!,
            spu_code: spu.spu_code || undefined,
            name: spu.name,
            description: spu.description || undefined,
            origin: spu.origin || "中国",
            hs_code: spu.hs_code || undefined,
            brand: spu.brand || undefined,
            certifications: spu.certifications.length > 0 ? spu.certifications : undefined,
            selling_points: spu.selling_points || undefined,
            source_lang: locale,
            is_featured: spu.is_featured,
            supply_mode: spu.supply_mode,
            unit: spu.unit,
            currency: spu.currency,
            lead_time_min: spu.lead_time_min ? Number(spu.lead_time_min) : undefined,
            lead_time_max: spu.lead_time_max ? Number(spu.lead_time_max) : undefined,
            packing_quantity: spu.packing_quantity ? Number(spu.packing_quantity) : undefined,
            gross_weight_kg: spu.gross_weight_kg ? Number(spu.gross_weight_kg) : undefined,
            volume_cbm: spu.volume_cbm ? Number(spu.volume_cbm) : undefined,
            can_consolidate: spu.can_consolidate,
            cargo_type: spu.cargo_type || undefined,
            attributes: spuAttrs.length > 0 ? spuAttrs : undefined,
            skus: aggregateSkus,
          });
          productId = result.id;
          skuMappings = result.skus;
        } else {
          // 无 SKU → SPU-only 建壳
          const result = await operatorProductsApi.create({
            category_code: category.level3Code!,
            spu_code: spu.spu_code || undefined,
            name: spu.name,
            description: spu.description || undefined,
            origin: spu.origin || "中国",
            hs_code: spu.hs_code || undefined,
            brand: spu.brand || undefined,
            certifications: spu.certifications.length > 0 ? spu.certifications : undefined,
            selling_points: spu.selling_points || undefined,
            source_lang: locale,
            is_featured: spu.is_featured,
            supply_mode: spu.supply_mode,
            unit: spu.unit,
            currency: spu.currency,
            lead_time_min: spu.lead_time_min ? Number(spu.lead_time_min) : undefined,
            lead_time_max: spu.lead_time_max ? Number(spu.lead_time_max) : undefined,
            packing_quantity: spu.packing_quantity ? Number(spu.packing_quantity) : undefined,
            gross_weight_kg: spu.gross_weight_kg ? Number(spu.gross_weight_kg) : undefined,
            volume_cbm: spu.volume_cbm ? Number(spu.volume_cbm) : undefined,
            can_consolidate: spu.can_consolidate,
            cargo_type: spu.cargo_type || undefined,
            attributes: spuAttrs.length > 0 ? spuAttrs : undefined,
          });
          productId = result.id;
        }
        setCreatedProductId(productId);
      }

      // 2) 上传 SPU 图片
      for (const file of spuImageFiles) {
        await operatorProductsApi.uploadImage(productId, file);
      }

      // 3) 上传 SKU 图片（按 client_id 映射找到后端 sku_id）
      if (!existingId && skuMappings) {
        for (const sku of skus) {
          if (sku.imageFiles.length === 0) continue;
          const mapping = skuMappings.find((m) => m.client_id === sku._clientId);
          if (mapping) {
            for (const file of sku.imageFiles) {
              await operatorProductsApi.uploadImage(productId, file, mapping.id);
            }
          }
        }
      }

      // 4) 发布（如果是上架）
      if (publish) {
        await operatorProductsApi.updateStatus(productId, { status: "ACTIVE" });
      }

      // 成功 → 清草稿缓存 + 跳转
      clearDraft();
      toastSuccess(publish ? t("success_publish") : t("success_draft"));
      // 草稿 → 编辑态（后续增量在详情页完成）；上架 → 查看态
      const editQuery = publish ? "" : "?edit=true";
      router.push(`/${locale}/operator/products/${productId}${editQuery}`);
    } catch (err: unknown) {
      const reason = extractErrorMsg(err);
      if (productId != null) {
        // SPU 已创建但后续步骤失败 → 清草稿（防止重复创建）+ 保留 productId 用于 retry
        clearDraft();
        setCreatedProductId(productId);
        toastWarning(t("error_draft_saved_partial", { reason }));
      } else {
        toastError(reason);
      }
    } finally {
      setSubmitting(false);
    }
  }, [category, spu, skus, spuImageFiles, t, extractErrorMsg, locale, router, toastSuccess, toastWarning, toastError, createdProductId]);

  // ---------- 渲染 ----------
  return (
    <div className="relative min-h-screen bg-slate-50">
      {/* 锚点导航 */}
      <SectionAnchorNav sectionRefs={sectionRefs} />

      <div className="mx-auto max-w-5xl px-4 py-6 pb-24">
        {/* ① 基本信息 */}
        {/* 草稿恢复提示 */}
        {pendingDraft && !draftRestored && (
          <div className="mb-5 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <span className="text-sm text-amber-800">{t("draft_found")}</span>
            <div className="flex gap-2">
              <button type="button" onClick={discardDraft} className="rounded px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">{t("draft_discard")}</button>
              <button type="button" onClick={restoreDraft} className="rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700">{t("draft_restore")}</button>
            </div>
          </div>
        )}

        <section ref={sectionRefs.basic} id="section-basic" className="mb-7">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">① {t("section_basic_title")}</h3>
            <span className="text-xs text-slate-500">{t("section_basic_subtitle")}</span>
          </div>
          <div className="mb-3.5 rounded border-l-[3px] border-blue-500 bg-blue-50 px-2.5 py-1.5 text-xs text-slate-500">
            {t("section_basic_hint")}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
              {/* 品类级联 - 全宽 */}
              <div className="sm:col-span-2" data-field-error={!!fieldErrors.category || undefined}>
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="text-sm font-medium text-slate-700">
                    {t("field_category")} <span className="text-red-500">*</span>
                  </span>
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
                    {t("field_category_hint")}
                  </span>
                </div>
                <div className={fieldErrors.category ? "rounded-md ring-1 ring-red-500" : ""}>
                  <CategoryCascader value={category} onChange={handleCategoryChange} required />
                </div>
                {fieldErrors.category && <p className="mt-1 text-xs text-red-500">{fieldErrors.category}</p>}
                {attrLoading && (
                  <p className="mt-1 text-xs text-slate-400">{t("attr_loading")}</p>
                )}
              </div>

              {/* SPU 编码 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_spu_code")}</label>
                <span className="ml-1 text-[10px] text-slate-400">{t("field_spu_code_hint")}</span>
                <input
                  type="text"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.spu_code}
                  onChange={(e) => updateSpu("spu_code", e.target.value)}
                  maxLength={50}
                  placeholder="AG-10-001-003-001"
                />
              </div>

              {/* 商品名称 */}
              <div data-field-error={!!fieldErrors.name || undefined}>
                <label className="text-sm font-medium text-slate-700">
                  {t("field_name")} <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  className={`mt-1.5 h-9 w-full rounded-md border bg-white px-3 text-sm focus:outline-none focus:ring-2 ${
                    fieldErrors.name
                      ? "border-red-500 focus:border-red-500 focus:ring-red-500/20"
                      : "border-slate-200 focus:border-blue-500 focus:ring-blue-500/20"
                  }`}
                  value={spu.name}
                  onChange={(e) => updateSpu("name", e.target.value)}
                  maxLength={200}
                />
                {fieldErrors.name && <p className="mt-1 text-xs text-red-500">{fieldErrors.name}</p>}
              </div>

              {/* 产地 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_origin")}</label>
                <input
                  type="text"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.origin}
                  onChange={(e) => updateSpu("origin", e.target.value)}
                />
              </div>

              {/* 品牌 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_brand")}</label>
                <input
                  type="text"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.brand}
                  onChange={(e) => updateSpu("brand", e.target.value)}
                />
              </div>

              {/* HS 编码 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_hs_code")}</label>
                <input
                  type="text"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.hs_code}
                  onChange={(e) => updateSpu("hs_code", e.target.value)}
                />
              </div>

              {/* 计量单位 */}
              <div>
                <label className="text-sm font-medium text-slate-700">
                  {t("field_unit")} <span className="text-red-500">*</span>
                </label>
                <select
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.unit}
                  onChange={(e) => updateSpu("unit", e.target.value as SkuUnitCode)}
                >
                  {SKU_UNITS.map((u) => (
                    <option key={u} value={u}>
                      {u} - {tUnit(u)}
                    </option>
                  ))}
                </select>
              </div>

              {/* 币种 */}
              <div>
                <label className="text-sm font-medium text-slate-700">
                  {t("field_currency")} <span className="text-red-500">*</span>
                </label>
                <select
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.currency}
                  onChange={(e) => updateSpu("currency", e.target.value)}
                >
                  <option value="TZS">TZS</option>
                  <option value="USD">USD</option>
                  <option value="CNY">CNY</option>
                </select>
              </div>

              {/* ── 物流参数 ── */}
              <div className="sm:col-span-2 mt-2 mb-1">
                <h4 className="text-sm font-medium text-slate-600 border-b border-slate-100 pb-1.5">
                  {t("logistics_title")}
                </h4>
              </div>

              {/* 交期范围 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_lead_time_min")}</label>
                <input
                  type="number"
                  min="0"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.lead_time_min}
                  onChange={(e) => updateSpu("lead_time_min", e.target.value)}
                  placeholder={t("field_lead_time_min_placeholder")}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_lead_time_max")}</label>
                <input
                  type="number"
                  min="0"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.lead_time_max}
                  onChange={(e) => updateSpu("lead_time_max", e.target.value)}
                  placeholder={t("field_lead_time_max_placeholder")}
                />
              </div>

              {/* 每箱装量 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_packing_quantity")}</label>
                <input
                  type="number"
                  min="1"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.packing_quantity}
                  onChange={(e) => updateSpu("packing_quantity", e.target.value)}
                />
              </div>

              {/* 单件毛重 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_gross_weight_kg")}</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.gross_weight_kg}
                  onChange={(e) => updateSpu("gross_weight_kg", e.target.value)}
                  placeholder="kg"
                />
              </div>

              {/* 单件体积 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_volume_cbm")}</label>
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.volume_cbm}
                  onChange={(e) => updateSpu("volume_cbm", e.target.value)}
                  placeholder="CBM"
                />
              </div>

              {/* 货物类型 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_cargo_type")}</label>
                <input
                  type="text"
                  maxLength={20}
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.cargo_type}
                  onChange={(e) => updateSpu("cargo_type", e.target.value)}
                />
              </div>

              {/* 可拼柜 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_can_consolidate")}</label>
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => updateSpu("can_consolidate", !spu.can_consolidate)}
                    className={`relative h-5 w-10 rounded-full transition-colors ${spu.can_consolidate ? "bg-blue-500" : "bg-slate-300"}`}
                  >
                    <div
                      className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${spu.can_consolidate ? "translate-x-5" : "translate-x-0.5"}`}
                    />
                  </button>
                </div>
              </div>

              {/* 认证 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_certifications")}</label>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {spu.certifications.map((cert) => (
                    <span
                      key={cert}
                      className="inline-flex items-center gap-1 rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-800"
                    >
                      {cert}
                      <button
                        type="button"
                        onClick={() => removeCertification(cert)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      className="h-6 w-20 rounded border border-slate-200 px-2 text-xs focus:border-blue-500 focus:outline-none"
                      value={certInput}
                      onChange={(e) => setCertInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCertification())}
                      placeholder="PVoC"
                    />
                    <button
                      type="button"
                      onClick={addCertification}
                      className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-200"
                    >
                      {t("field_certifications_add")}
                    </button>
                  </div>
                </div>
              </div>

              {/* 卖点 - 全宽 */}
              <div className="sm:col-span-2">
                <label className="text-sm font-medium text-slate-700">{t("field_selling_points")}</label>
                <input
                  type="text"
                  className="mt-1.5 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.selling_points}
                  onChange={(e) => updateSpu("selling_points", e.target.value)}
                />
              </div>

              {/* 商品描述 - 全宽 */}
              <div className="sm:col-span-2">
                <label className="text-sm font-medium text-slate-700">{t("field_description")}</label>
                <textarea
                  className="mt-1.5 min-h-[80px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  value={spu.description}
                  onChange={(e) => updateSpu("description", e.target.value)}
                />
              </div>

              {/* 是否推荐 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_is_featured")}</label>
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => updateSpu("is_featured", !spu.is_featured)}
                    className={`relative h-5 w-10 rounded-full transition-colors ${spu.is_featured ? "bg-blue-500" : "bg-slate-300"}`}
                  >
                    <div
                      className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${spu.is_featured ? "translate-x-5" : "translate-x-0.5"}`}
                    />
                  </button>
                </div>
              </div>

              {/* 履约模式 */}
              <div>
                <label className="text-sm font-medium text-slate-700">{t("field_supply_mode")}</label>
                <div className="mt-2 flex gap-4">
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="supply_mode"
                      value="SUPPLIER_DIRECT"
                      checked={spu.supply_mode === "SUPPLIER_DIRECT"}
                      onChange={() => updateSpu("supply_mode", "SUPPLIER_DIRECT")}
                      className="h-4 w-4 text-blue-600"
                    />
                    {t("field_supply_mode_supplier_direct")}
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="supply_mode"
                      value="PLATFORM_STOCK"
                      checked={spu.supply_mode === "PLATFORM_STOCK"}
                      onChange={() => updateSpu("supply_mode", "PLATFORM_STOCK")}
                      className="h-4 w-4 text-blue-600"
                    />
                    {t("field_supply_mode_platform_stock")}
                  </label>
                </div>
              </div>

              {/* scope=SPU 属性（从模板动态渲染） */}
              {spuTemplates.length > 0 && (
                <div className="sm:col-span-2">
                  <h4 className="mb-2 border-b border-slate-100 pb-1.5 text-sm font-medium text-slate-600">
                    {t("sku_section_attrs")}
                    <span className="ml-1.5 text-[10px] font-normal text-slate-400">
                      SPU · {spuTemplates.length}
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                    {spuTemplates.map((tpl) => (
                      <div key={tpl.attr_key}>
                        <label className="text-xs text-slate-500">
                          {tpl.display_name}
                          {tpl.is_required && <span className="text-red-500"> *</span>}
                          {tpl.attr_unit && <span className="text-slate-400"> ({tpl.attr_unit})</span>}
                        </label>
                        <input
                          type={tpl.attr_type === "number" ? "number" : "text"}
                          className="mt-1 h-8 w-full rounded border border-slate-200 px-2 text-xs focus:border-blue-500 focus:outline-none"
                          value={spu.spuAttributes[tpl.attr_key] ?? ""}
                          onChange={(e) =>
                            updateSpu("spuAttributes", { ...spu.spuAttributes, [tpl.attr_key]: e.target.value })
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ② SKU 明细 */}
        <section ref={sectionRefs.sku} id="section-sku" className="mb-7">
          <div className="mb-1 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-slate-800">② {t("section_sku_title")}</h3>
              <span className="text-xs text-slate-500">{t("section_sku_subtitle")}</span>
            </div>
            <Button
              onClick={addSku}
              disabled={!isLeafSelected}
              size="sm"
            >
              {t("sku_add")}
            </Button>
          </div>
          <div className="mb-3.5 rounded border-l-[3px] border-amber-500 bg-amber-50 px-2.5 py-1.5 text-xs text-slate-500">
            {t("section_sku_hint")}
          </div>
          {fieldErrors.skus && (
            <div data-field-error="true" className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
              {fieldErrors.skus}
            </div>
          )}

          {skus.map((sku, idx) => (
            <SkuCard
              key={sku._clientId}
              sku={sku}
              index={idx}
              currency={spu.currency}
              templates={skuTemplates}
              onUpdate={(patch) => updateSku(sku._clientId, patch)}
              onRemove={() => removeSku(sku._clientId)}
              onSetDefault={() => setDefaultSku(sku._clientId)}
              onOpenTiers={() => setTierModalSkuId(sku._clientId)}
              error={null}
              fieldErrors={fieldErrors}
              t={t}
              tUnit={tUnit}
            />
          ))}

          {/* 添加 SKU 占位 */}
          <button
            type="button"
            onClick={addSku}
            disabled={!isLeafSelected}
            className="w-full rounded-xl border-2 border-dashed border-slate-300 py-5 text-center hover:border-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="text-sm font-medium text-blue-600">{t("sku_add")}</span>
            <span className="mt-1 block text-xs text-slate-400">{t("sku_add_hint")}</span>
          </button>
        </section>

        {/* ③ 商品图片 */}
        <section ref={sectionRefs.images} id="section-images" className="mb-7">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-800">③ {t("section_images_title")}</h3>
            <span className="text-xs text-slate-500">{t("section_images_subtitle")}</span>
          </div>
          <div className="mb-3.5 rounded border-l-[3px] border-pink-500 bg-pink-50 px-2.5 py-1.5 text-xs text-slate-500">
            {t("section_images_hint")}
          </div>
          <SpuImageUploader files={spuImageFiles} onChange={(files) => { setSpuImageFiles(files); clearFieldError("images"); }} t={t} />
          {fieldErrors.images && (
            <div data-field-error="true" className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
              {fieldErrors.images}
            </div>
          )}
        </section>
      </div>

      {/* 底部操作栏 */}
      <div className="fixed bottom-0 left-0 right-0 z-10 border-t-2 border-slate-200 bg-white px-5 py-3.5">
        <div className="mx-auto flex max-w-5xl justify-end gap-2.5">
          {/* 字段级错误摘要 */}
          {/* 部分成功（SPU 已创建）→ 跳转按钮 */}
          {createdProductId != null && Object.keys(fieldErrors).length === 0 && (
            <button
              type="button"
              onClick={() => router.push(`/${locale}/operator/products/${createdProductId}?edit=true`)}
              className="mr-auto self-center rounded border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
            >
              {t("error_draft_go_detail")}
            </button>
          )}
          <Button
            variant="outline"
            onClick={() => handleSubmit(false)}
            disabled={submitting}
          >
            {submitting ? t("btn_saving") : t("btn_save_draft")}
          </Button>
          <Button
            onClick={() => handleSubmit(true)}
            disabled={submitting}
          >
            {submitting ? t("btn_publishing") : t("btn_publish")}
          </Button>
        </div>
      </div>

      {/* 阶梯价弹窗 */}
      {tierModalSkuId && (
        <PriceTierModal
          tiers={skus.find((s) => s._clientId === tierModalSkuId)?.price_tiers ?? []}
          moq={Number(skus.find((s) => s._clientId === tierModalSkuId)?.moq) || 1}
          currency={spu.currency}
          onConfirm={(tiers) => {
            updateSku(tierModalSkuId, { price_tiers: tiers });
            setTierModalSkuId(null);
          }}
          onCancel={() => setTierModalSkuId(null)}
          t={t}
        />
      )}
    </div>
  );
}
