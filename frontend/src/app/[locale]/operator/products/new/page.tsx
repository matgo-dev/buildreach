"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Save } from "lucide-react";

import { operatorProductApi, categoryApi, type AttrTemplate } from "@/lib/productApi";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { FieldError } from "@/components/form/FieldError";
import { validateAll, extractFieldErrors, errorSummary, type FieldRules } from "@/lib/formValidation";
import { Package, Upload, X, Star } from "lucide-react";

// 前端校验规则
const PRODUCT_RULES: FieldRules = {
  category_code: [{ required: true, message: "请选择品类" }],
  name: [{ required: true, message: "请填写商品名称" }],
  price_min: [{ required: true, message: "请填写最低价" }, { min: 0.01, message: "最低价必须大于 0" }],
  price_max: [{ required: true, message: "请填写最高价" }, { min: 0.01, message: "最高价必须大于 0" }],
  moq: [{ required: true, message: "请填写起订量" }, { min: 1, message: "起订量至少为 1" }],
  unit: [{ required: true, message: "请选择计量单位" }],
};

const STEPS = ["基础信息", "品类属性", "图片上传", "预览确认"];

type CategoryItem = { code: string; name_zh: string; name_en: string; level: number };

type FormData = {
  l1_code: string;
  l2_code: string;
  l3_code: string;
  category_code: string;
  name: string;
  description: string;
  price_min: string;
  price_max: string;
  currency: string;
  unit: string;
  moq: string;
  lead_time_min: string;
  lead_time_max: string;
  origin: string;
  hs_code: string;
  brand: string;
  certifications: string[];
  is_featured: boolean;
  attributes: { attr_key: string; attr_value: string; attr_unit: string }[];
};

const CERT_OPTIONS = ["PVoC", "CoC", "ISO9001", "CE", "SABS", "KEBS"];
const UNIT_OPTIONS = ["pcs", "sets", "meters", "kg", "rolls", "bags", "boxes"];

export default function CreateProductPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [l1List, setL1List] = useState<CategoryItem[]>([]);
  const [l2List, setL2List] = useState<CategoryItem[]>([]);
  const [l3List, setL3List] = useState<CategoryItem[]>([]);
  const [attrTemplates, setAttrTemplates] = useState<AttrTemplate[]>([]);

  const [form, setForm] = useState<FormData>({
    l1_code: "",
    l2_code: "",
    l3_code: "",
    category_code: "",
    name: "",
    description: "",
    price_min: "",
    price_max: "",
    currency: "USD",
    unit: "pcs",
    moq: "1",
    lead_time_min: "",
    lead_time_max: "",
    origin: "China",
    hs_code: "",
    brand: "",
    certifications: [],
    is_featured: false,
    attributes: [],
  });

  // 拉 L1 品类
  useEffect(() => {
    api.get<CategoryItem[]>("/api/v1/categories?level=1&is_active=true").then(setL1List).catch(console.error);
  }, []);

  // L1 变化 → 拉 L2，清空 L2/L3
  useEffect(() => {
    if (!form.l1_code) {
      setL2List([]);
      setL3List([]);
      setForm((f) => ({ ...f, l2_code: "", l3_code: "", category_code: form.l1_code }));
      return;
    }
    setForm((f) => ({ ...f, l2_code: "", l3_code: "", category_code: form.l1_code }));
    setL3List([]);
    api.get<CategoryItem[]>(`/api/v1/categories?parent_code=${form.l1_code}&is_active=true`)
      .then((items) => {
        setL2List(items);
        // 如果没有 L2 子级，最终分类就是 L1
        if (items.length === 0) {
          setForm((f) => ({ ...f, category_code: form.l1_code }));
        }
      })
      .catch(console.error);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.l1_code]);

  // L2 变化 → 拉 L3，清空 L3
  useEffect(() => {
    if (!form.l2_code) {
      setL3List([]);
      // 有 L2 列表但没选 → category_code 保持 L1
      if (form.l1_code) setForm((f) => ({ ...f, l3_code: "", category_code: form.l1_code }));
      return;
    }
    setForm((f) => ({ ...f, l3_code: "", category_code: form.l2_code }));
    api.get<CategoryItem[]>(`/api/v1/categories?parent_code=${form.l2_code}&is_active=true`)
      .then((items) => {
        setL3List(items);
        if (items.length === 0) {
          setForm((f) => ({ ...f, category_code: form.l2_code }));
        }
      })
      .catch(console.error);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.l2_code]);

  // L3 变化 → 设置最终 category_code
  useEffect(() => {
    if (form.l3_code) {
      setForm((f) => ({ ...f, category_code: form.l3_code }));
    } else if (form.l2_code) {
      setForm((f) => ({ ...f, category_code: form.l2_code }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.l3_code]);

  // category_code 变化 → 拉属性模板
  useEffect(() => {
    if (!form.category_code) {
      setAttrTemplates([]);
      return;
    }
    categoryApi.attrTemplates(form.category_code).then((tpls) => {
      setAttrTemplates(tpls);
      setForm((f) => ({
        ...f,
        attributes: tpls.map((t) => ({
          attr_key: t.attr_key,
          attr_value: "",
          attr_unit: t.attr_unit || "",
        })),
      }));
    }).catch(console.error);
  }, [form.category_code]);

  const updateField = (field: keyof FormData, value: any) => {
    setForm((f) => ({ ...f, [field]: value }));
    // 清除该字段的错误
    if (errors[field]) {
      setErrors((e) => { const n = { ...e }; delete n[field]; return n; });
    }
  };

  const updateAttr = (idx: number, value: string) => {
    setForm((f) => {
      const attrs = [...f.attributes];
      attrs[idx] = { ...attrs[idx], attr_value: value };
      return { ...f, attributes: attrs };
    });
  };

  const toggleCert = (cert: string) => {
    setForm((f) => ({
      ...f,
      certifications: f.certifications.includes(cert)
        ? f.certifications.filter((c) => c !== cert)
        : [...f.certifications, cert],
    }));
  };

  // 图片管理
  const handleAddImages = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const total = imageFiles.length + files.length;
    if (total > 8) {
      alert("最多上传 8 张图片");
      return;
    }
    const newFiles = [...imageFiles, ...files];
    setImageFiles(newFiles);
    // 生成预览
    const newPreviews = [...imagePreviews];
    files.forEach((f) => newPreviews.push(URL.createObjectURL(f)));
    setImagePreviews(newPreviews);
    e.target.value = "";
  };

  const handleRemoveImage = (idx: number) => {
    URL.revokeObjectURL(imagePreviews[idx]);
    setImageFiles((fs) => fs.filter((_, i) => i !== idx));
    setImagePreviews((ps) => ps.filter((_, i) => i !== idx));
  };

  const handleSave = async (asDraft: boolean) => {
    // 前端校验
    const frontErrors = validateAll(form as unknown as Record<string, unknown>, PRODUCT_RULES);
    if (Object.keys(frontErrors).length > 0) {
      setErrors(frontErrors);
      setStep(0); // 跳回基础信息步骤
      return;
    }

    setSaving(true);
    setErrors({});
    try {
      // 1. 创建商品
      const payload: Record<string, unknown> = {
        category_code: form.category_code,
        name: form.name,
        description: form.description || null,
        price_min: parseFloat(form.price_min),
        price_max: parseFloat(form.price_max),
        currency: form.currency,
        unit: form.unit,
        moq: parseInt(form.moq),
        lead_time_days: form.lead_time_max ? parseInt(form.lead_time_max) : null,
        origin: form.origin,
        hs_code: form.hs_code || null,
        brand: form.brand || null,
        certifications: form.certifications,
        is_featured: form.is_featured,
        status: asDraft ? "DRAFT" : "DRAFT",
        attributes: form.attributes
          .filter((a) => a.attr_value)
          .map((a, i) => ({ ...a, sort_order: i })),
      };
      const res = await operatorProductApi.create(payload);

      // 2. 上传图片（第一张自动设为主图）
      for (const file of imageFiles) {
        await operatorProductApi.uploadImage(res.id, file);
      }

      router.push(`/operator/products/${res.id}`);
    } catch (e: any) {
      // 解析后端字段级错误
      const fieldErrors = extractFieldErrors(e);
      if (Object.keys(fieldErrors).length > 0) {
        setErrors(fieldErrors);
        setStep(0); // 跳回基础信息步骤显示错误
      } else {
        alert(e.message || "创建失败，请检查表单内容");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <AdminPageHeader
        titleZh="创建商品"
        titleEn="Create Product"
        subtitle="填写商品信息，添加到商品目录"
        breadcrumbs={[
          { label: "运营后台", href: "/operator/dashboard" },
          { label: "商品中心", href: "/operator/products" },
          { label: "新增商品" },
        ]}
        actions={
          <button onClick={() => router.back()} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-600 hover:bg-slate-50">
            <ArrowLeft className="mr-1 inline h-4 w-4" />返回
          </button>
        }
      />

      {/* Step Indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <button
              onClick={() => setStep(i)}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                i === step
                  ? "bg-blue-600 text-white"
                  : i < step
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-500"
              }`}
            >
              {i < step ? <Check className="h-4 w-4" /> : <span>{i + 1}</span>}
              {s}
            </button>
            {i < STEPS.length - 1 && <div className="h-px w-8 bg-slate-200" />}
          </div>
        ))}
      </div>

      {/* Form Content */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        {step === 0 && (
          <div className="grid grid-cols-2 gap-6">
            {/* 错误汇总 */}
            {Object.keys(errors).length > 0 && (
              <div className="col-span-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                <p className="font-medium">请修正以下问题：</p>
                <ul className="mt-1 list-inside list-disc text-[12px]">
                  {Object.values(errors).map((msg, i) => <li key={i}>{msg}</li>)}
                </ul>
              </div>
            )}
            {/* 三级品类联动 */}
            <div className="col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">所属品类 / Category *</label>
              <div className="grid grid-cols-3 gap-3">
                {/* L1 一级品类 */}
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={form.l1_code}
                  onChange={(e) => updateField("l1_code", e.target.value)}
                >
                  <option value="">一级品类...</option>
                  {l1List.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name_zh} / {c.name_en}
                    </option>
                  ))}
                </select>
                {/* L2 二级品类 */}
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400"
                  value={form.l2_code}
                  onChange={(e) => updateField("l2_code", e.target.value)}
                  disabled={l2List.length === 0}
                >
                  <option value="">{l2List.length === 0 ? (form.l1_code ? "无子分类" : "请先选一级") : "二级品类..."}</option>
                  {l2List.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name_zh} / {c.name_en}
                    </option>
                  ))}
                </select>
                {/* L3 三级品类 */}
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400"
                  value={form.l3_code}
                  onChange={(e) => updateField("l3_code", e.target.value)}
                  disabled={l3List.length === 0}
                >
                  <option value="">{l3List.length === 0 ? (form.l2_code ? "无子分类" : "请先选二级") : "三级品类..."}</option>
                  {l3List.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name_zh} / {c.name_en}
                    </option>
                  ))}
                </select>
              </div>
              {form.category_code && (
                <p className="mt-1 text-xs text-slate-400">
                  最终品类编码：<span className="font-mono text-blue-600">{form.category_code}</span>
                  {" "}（SKU 编码将由系统自动生成）
                </p>
              )}
            </div>

            {/* Brand */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">品牌</label>
              <input
                type="text"
                placeholder="如 OEM"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.brand}
                onChange={(e) => updateField("brand", e.target.value)}
              />
            </div>

            {/* Name EN */}
            <div className="col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">商品名称 / Product Name *</label>
              <input
                type="text"
                placeholder="如 LED Panel Light 36W 600x600mm"
                className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${errors.name ? "border-red-400 focus:border-red-500 focus:ring-red-500" : "border-slate-200 focus:border-blue-500 focus:ring-blue-500"}`}
                value={form.name}
                onChange={(e) => updateField("name", e.target.value)}
              />
              <FieldError error={errors.name} />
            </div>

            {/* Description */}
            <div className="col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">商品描述 / Description</label>
              <textarea
                rows={3}
                placeholder="商品描述..."
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.description}
                onChange={(e) => updateField("description", e.target.value)}
              />
            </div>

            {/* Price Range */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最低价（USD）*</label>
              <input
                type="number"
                step="0.01"
                min="0"
                className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${errors.price_min ? "border-red-400 focus:border-red-500 focus:ring-red-500" : "border-slate-200 focus:border-blue-500 focus:ring-blue-500"}`}
                value={form.price_min}
                onChange={(e) => updateField("price_min", e.target.value)}
              />
              <FieldError error={errors.price_min} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最高价（USD）*</label>
              <input
                type="number"
                step="0.01"
                min="0"
                className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${errors.price_max ? "border-red-400 focus:border-red-500 focus:ring-red-500" : "border-slate-200 focus:border-blue-500 focus:ring-blue-500"}`}
                value={form.price_max}
                onChange={(e) => updateField("price_max", e.target.value)}
              />
              <FieldError error={errors.price_max} />
            </div>

            {/* MOQ + Unit */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最小起订量 *</label>
              <input
                type="number"
                min="1"
                className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${errors.moq ? "border-red-400 focus:border-red-500 focus:ring-red-500" : "border-slate-200 focus:border-blue-500 focus:ring-blue-500"}`}
                value={form.moq}
                onChange={(e) => updateField("moq", e.target.value)}
              />
              <FieldError error={errors.moq} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">计量单位 *</label>
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.unit}
                onChange={(e) => updateField("unit", e.target.value)}
              >
                {UNIT_OPTIONS.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </div>

            {/* Lead time (min + max) */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最短交期（天）</label>
              <input
                type="number"
                min="0"
                placeholder="如 3"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.lead_time_min}
                onChange={(e) => updateField("lead_time_min", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最长交期（天）</label>
              <input
                type="number"
                min="0"
                placeholder="如 7"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.lead_time_max}
                onChange={(e) => updateField("lead_time_max", e.target.value)}
              />
            </div>

            {/* Origin */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">产地</label>
              <input
                type="text"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.origin}
                onChange={(e) => updateField("origin", e.target.value)}
              />
            </div>

            {/* HS Code */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">HS 编码</label>
              <input
                type="text"
                placeholder="如 9405.42"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.hs_code}
                onChange={(e) => updateField("hs_code", e.target.value)}
              />
            </div>

            {/* Featured */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="featured"
                checked={form.is_featured}
                onChange={(e) => updateField("is_featured", e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="featured" className="text-sm font-medium text-slate-700">精选推荐</label>
            </div>

            {/* Certifications */}
            <div className="col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-slate-700">认证资质</label>
              <div className="flex flex-wrap gap-2">
                {CERT_OPTIONS.map((cert) => (
                  <button
                    key={cert}
                    type="button"
                    onClick={() => toggleCert(cert)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      form.certifications.includes(cert)
                        ? "bg-blue-100 text-blue-700 ring-1 ring-blue-300"
                        : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    {cert}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            {attrTemplates.length === 0 ? (
              <p className="text-sm text-slate-400">
                {form.category_code
                  ? "该品类暂无属性模板定义。"
                  : "请先在第一步选择品类。"}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {attrTemplates.map((tpl, idx) => (
                  <div key={tpl.attr_key}>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">
                      {tpl.display_name}
                      {tpl.is_required && <span className="text-red-500"> *</span>}
                      {tpl.attr_unit && (
                        <span className="ml-1 text-xs text-slate-400">({tpl.attr_unit})</span>
                      )}
                    </label>
                    {tpl.attr_type === "select" && tpl.options ? (
                      <select
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        value={form.attributes[idx]?.attr_value || ""}
                        onChange={(e) => updateAttr(idx, e.target.value)}
                      >
                        <option value="">Select...</option>
                        {(Array.isArray(tpl.options) ? tpl.options : []).map((opt: string) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : tpl.attr_type === "boolean" ? (
                      <select
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        value={form.attributes[idx]?.attr_value || ""}
                        onChange={(e) => updateAttr(idx, e.target.value)}
                      >
                        <option value="">Select...</option>
                        <option value="Yes">Yes</option>
                        <option value="No">No</option>
                      </select>
                    ) : (
                      <input
                        type={tpl.attr_type === "number" ? "number" : "text"}
                        placeholder={tpl.display_name}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        value={form.attributes[idx]?.attr_value || ""}
                        onChange={(e) => updateAttr(idx, e.target.value)}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-slate-900">商品图片 / Product Images</h3>
            <p className="text-[13px] text-slate-500">上传商品图片，第一张自动设为主图。支持 jpg/png/webp，单张不超过 5MB，最多 8 张。</p>

            {/* 上传区域 */}
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-8 transition-colors hover:border-blue-400 hover:bg-blue-50/30">
              <Upload className="mb-2 h-8 w-8 text-slate-400" />
              <span className="text-[13px] font-medium text-slate-600">点击上传图片 / Click to upload</span>
              <span className="mt-1 text-[11px] text-slate-400">支持 JPG / PNG / WebP，最多 8 张</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                onChange={handleAddImages}
              />
            </label>

            {/* 图片预览 */}
            {imagePreviews.length > 0 && (
              <div className="grid grid-cols-4 gap-3">
                {imagePreviews.map((src, idx) => (
                  <div key={idx} className="group relative">
                    <img
                      src={src}
                      alt={`图片 ${idx + 1}`}
                      className="h-32 w-full rounded-lg border border-slate-200 object-cover"
                    />
                    {idx === 0 && (
                      <span className="absolute left-1.5 top-1.5 rounded bg-blue-600 px-1.5 py-0.5 text-[10px] font-medium text-white">
                        <Star className="mr-0.5 inline h-2.5 w-2.5" />主图
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveImage(idx)}
                      className="absolute right-1.5 top-1.5 hidden rounded-full bg-red-500/80 p-1 text-white group-hover:block"
                    >
                      <X className="h-3 w-3" />
                    </button>
                    <p className="mt-1 text-center text-[10px] text-slate-400">
                      {idx === 0 ? "主图 / Main" : `图片 ${idx + 1}`}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {imagePreviews.length === 0 && (
              <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-slate-200 text-slate-300">
                <div className="text-center">
                  <Package className="mx-auto h-8 w-8" />
                  <p className="mt-1 text-[12px]">暂未上传图片</p>
                </div>
              </div>
            )}

            <p className="text-[11px] text-slate-400">
              已选择 {imageFiles.length} / 8 张。图片将在保存时自动压缩到 800×800 正方形。
            </p>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-slate-900">预览确认 / Review</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-slate-500">品类编码：</span> <span className="font-mono font-medium">{form.category_code}</span></div>
              <div><span className="text-slate-500">SKU：</span> <span className="font-mono text-slate-400">系统自动生成</span></div>
              <div className="col-span-2"><span className="text-slate-500">商品名称：</span> <span className="font-medium">{form.name}</span></div>
              <div><span className="text-slate-500">价格区间：</span> <span className="font-medium">${form.price_min} - ${form.price_max}</span></div>
              <div><span className="text-slate-500">起订量：</span> <span className="font-medium">{form.moq} {form.unit}</span></div>
              <div><span className="text-slate-500">产地：</span> <span className="font-medium">{form.origin}</span></div>
              <div><span className="text-slate-500">品牌：</span> <span className="font-medium">{form.brand || "—"}</span></div>
              {form.certifications.length > 0 && (
                <div className="col-span-2">
                  <span className="text-slate-500">认证：</span>{" "}
                  {form.certifications.map((c) => (
                    <span key={c} className="ml-1 inline-block rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{c}</span>
                  ))}
                </div>
              )}
            </div>
            {form.attributes.filter((a) => a.attr_value).length > 0 && (
              <div className="mt-4">
                <h4 className="mb-2 text-sm font-medium text-slate-700">品类属性</h4>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  {form.attributes.filter((a) => a.attr_value).map((a) => (
                    <div key={a.attr_key} className="rounded-md bg-slate-50 px-3 py-2">
                      <span className="text-slate-500">{a.attr_key}:</span>{" "}
                      <span className="font-medium">{a.attr_value}{a.attr_unit ? ` ${a.attr_unit}` : ""}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* 图片预览 */}
            {imagePreviews.length > 0 && (
              <div className="mt-4">
                <h4 className="mb-2 text-sm font-medium text-slate-700">商品图片 ({imageFiles.length} 张)</h4>
                <div className="flex gap-2">
                  {imagePreviews.map((src, idx) => (
                    <img key={idx} src={src} alt="" className="h-16 w-16 rounded border border-slate-200 object-cover" />
                  ))}
                </div>
              </div>
            )}
            <p className="mt-4 text-xs text-slate-400">
              商品将保存为草稿，图片同步上传。保存后可绑定供应商，然后上架发布。
            </p>
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between">
        <button
          disabled={step === 0}
          onClick={() => setStep((s) => s - 1)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
        >
          <ArrowLeft className="h-4 w-4" />
          上一步
        </button>
        <div className="flex items-center gap-3">
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              下一步
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => handleSave(true)}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              <Save className="h-4 w-4" />
              {saving ? "保存中..." : "保存为草稿"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
