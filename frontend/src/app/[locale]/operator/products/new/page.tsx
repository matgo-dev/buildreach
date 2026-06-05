"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Save } from "lucide-react";

import { operatorProductApi, categoryApi, type AttrTemplate } from "@/lib/productApi";
import { api } from "@/lib/api";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const STEPS = ["基础信息", "品类属性", "预览确认"];

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
  lead_time_days: string;
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
    lead_time_days: "",
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

  const handleSave = async (asDraft: boolean) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        category_code: form.category_code,
        name: form.name,
        description: form.description || null,
        price_min: parseFloat(form.price_min),
        price_max: parseFloat(form.price_max),
        currency: form.currency,
        unit: form.unit,
        moq: parseInt(form.moq),
        lead_time_days: form.lead_time_days ? parseInt(form.lead_time_days) : null,
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
      router.push(`/operator/products/${res.id}`);
    } catch (e: any) {
      alert(e.message || "Failed to create product");
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
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.name}
                onChange={(e) => updateField("name", e.target.value)}
              />
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
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.price_min}
                onChange={(e) => updateField("price_min", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最高价（USD）*</label>
              <input
                type="number"
                step="0.01"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.price_max}
                onChange={(e) => updateField("price_max", e.target.value)}
              />
            </div>

            {/* MOQ + Unit */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">最小起订量 *</label>
              <input
                type="number"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.moq}
                onChange={(e) => updateField("moq", e.target.value)}
              />
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

            {/* Lead time + Origin */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">交期（天）</label>
              <input
                type="number"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={form.lead_time_days}
                onChange={(e) => updateField("lead_time_days", e.target.value)}
              />
            </div>
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
            <p className="mt-4 text-xs text-slate-400">
              商品将保存为草稿。保存后可上传图片、绑定供应商，然后上架发布。
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
