"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowUpCircle, ArrowDownCircle, Trash2, Upload, Plus, Package, Star,
  ChevronDown, ChevronRight, Search,
} from "lucide-react";

import {
  operatorProductApi,
  type ProductOperatorDetail,
  type SkuOperator,
  type SkuPriceTier,
  type SupplierRelationDetail,
} from "@/lib/productApi";
import { suppliersApi, type SupplierListItem } from "@/lib/api/suppliers";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { StatusBadge } from "@/components/products/StatusBadge";

const SKU_PAGE_SIZE = 10;

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = Number(params.id);
  const fileRef = useRef<HTMLInputElement>(null);

  const [product, setProduct] = useState<ProductOperatorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"skus" | "attrs" | "desc">("skus");

  // SKU 表格状态
  const [skuPage, setSkuPage] = useState(1);
  const [skuSearch, setSkuSearch] = useState("");
  const [expandedSkuId, setExpandedSkuId] = useState<number | null>(null);

  // 供货表单（挂 SKU）
  const [supplierFormSkuId, setSupplierFormSkuId] = useState<number | null>(null);
  const [sf, setSf] = useState({
    supplier_org_id: 0, supplier_org_name: "", supplier_price: "",
    supplier_currency: "CNY", cif_price_usd: "",
    supplier_moq: "", supplier_lead_time_days: "",
    pvoc_status: "", has_coc: false, is_preferred: false, notes: "",
  });
  const [supplierQuery, setSupplierQuery] = useState("");
  const [supplierOptions, setSupplierOptions] = useState<SupplierListItem[]>([]);
  const [showSupplierDropdown, setShowSupplierDropdown] = useState(false);
  const supplierSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchSuppliers = useCallback(async (q: string) => {
    try {
      const items = await suppliersApi.list({ q });
      setSupplierOptions(items);
      setShowSupplierDropdown(true);
    } catch { setSupplierOptions([]); }
  }, []);

  const handleSupplierQueryChange = (q: string) => {
    setSupplierQuery(q);
    setSf((f) => ({ ...f, supplier_org_id: 0, supplier_org_name: "" }));
    if (supplierSearchTimer.current) clearTimeout(supplierSearchTimer.current);
    if (q.length >= 1) {
      supplierSearchTimer.current = setTimeout(() => searchSuppliers(q), 300);
    } else {
      setShowSupplierDropdown(false);
    }
  };

  const selectSupplier = (s: SupplierListItem) => {
    setSf((f) => ({ ...f, supplier_org_id: s.id, supplier_org_name: s.name }));
    setSupplierQuery(s.name);
    setShowSupplierDropdown(false);
  };

  const resetSupplierForm = () => {
    setSupplierFormSkuId(null);
    setSf({ supplier_org_id: 0, supplier_org_name: "", supplier_price: "", supplier_currency: "CNY", cif_price_usd: "", supplier_moq: "", supplier_lead_time_days: "", pvoc_status: "", has_coc: false, is_preferred: false, notes: "" });
    setSupplierQuery("");
  };

  const fetchProduct = useCallback(async () => {
    setLoading(true);
    try { setProduct(await operatorProductApi.detail(productId)); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [productId]);

  useEffect(() => { fetchProduct(); }, [fetchProduct]);

  const handleStatus = async (s: string) => {
    try { await operatorProductApi.updateStatus(productId, s); fetchProduct(); }
    catch (e: any) { alert(e.message || "操作失败"); }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try { await operatorProductApi.uploadImage(productId, file); fetchProduct(); }
    catch (err: any) { alert(err.message || "上传失败"); }
    e.target.value = "";
  };

  const handleDeleteImage = async (imageId: number) => {
    if (!confirm("确定删除此图片？")) return;
    try { await operatorProductApi.deleteImage(productId, imageId); fetchProduct(); }
    catch (err: any) { alert(err.message || "删除失败"); }
  };

  const handleAddSupplier = async (skuId: number) => {
    if (!sf.supplier_org_id) { alert("请选择供应商"); return; }
    try {
      await operatorProductApi.addSupplier(productId, skuId, {
        supplier_org_id: sf.supplier_org_id,
        supplier_price: sf.supplier_price ? parseFloat(sf.supplier_price) : 0,
        supplier_currency: sf.supplier_currency,
        cif_price_usd: sf.cif_price_usd ? parseFloat(sf.cif_price_usd) : null,
        supplier_moq: sf.supplier_moq ? parseInt(sf.supplier_moq) : null,
        supplier_lead_time_days: sf.supplier_lead_time_days ? parseInt(sf.supplier_lead_time_days) : null,
        pvoc_status: sf.pvoc_status || null,
        has_coc: sf.has_coc, is_preferred: sf.is_preferred,
        notes: sf.notes || null,
      });
      resetSupplierForm();
      fetchProduct();
    } catch (err: any) { alert(err.message || "添加失败"); }
  };

  const handleRemoveSupplier = async (skuId: number, psId: number) => {
    if (!confirm("确定移除该供应商？")) return;
    try { await operatorProductApi.removeSupplier(productId, skuId, psId); fetchProduct(); }
    catch (err: any) { alert(err.message || "移除失败"); }
  };

  if (loading) return <div className="flex h-64 items-center justify-center text-slate-400">加载中...</div>;
  if (!product) return <div className="flex h-64 items-center justify-center text-slate-400">商品不存在</div>;

  const p = product;
  const images = p.images || [];
  const attrs = p.attributes || [];
  const allSkus = p.skus || [];

  // SKU 筛选 + 分页
  const filteredSkus = skuSearch
    ? allSkus.filter((s) =>
        s.sku_code.toLowerCase().includes(skuSearch.toLowerCase()) ||
        (s.name || "").toLowerCase().includes(skuSearch.toLowerCase()) ||
        (s.color || "").toLowerCase().includes(skuSearch.toLowerCase()) ||
        (s.material || "").toLowerCase().includes(skuSearch.toLowerCase())
      )
    : allSkus;
  const skuPages = Math.ceil(filteredSkus.length / SKU_PAGE_SIZE) || 1;
  const pagedSkus = filteredSkus.slice((skuPage - 1) * SKU_PAGE_SIZE, skuPage * SKU_PAGE_SIZE);

  return (
    <div className="space-y-5">
      <AdminPageHeader
        titleZh={p.name}
        titleEn={p.name_i18n ? Object.values(p.name_i18n).filter(Boolean).join(" / ") : p.spu_code}
        breadcrumbs={[
          { label: "运营后台", href: "/operator/dashboard" },
          { label: "商品中心", href: "/operator/products" },
          { label: "商品详情" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={p.status} />
            {p.status === "DRAFT" && (
              <button onClick={() => handleStatus("ACTIVE")} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-[13px] font-medium text-white hover:bg-emerald-700">
                <ArrowUpCircle className="h-4 w-4" /> 上架
              </button>
            )}
            {p.status === "ACTIVE" && (
              <button onClick={() => handleStatus("INACTIVE")} className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-[13px] font-medium text-white hover:bg-amber-600">
                <ArrowDownCircle className="h-4 w-4" /> 下架
              </button>
            )}
            {p.status === "INACTIVE" && (
              <button onClick={() => handleStatus("ACTIVE")} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-[13px] font-medium text-white hover:bg-emerald-700">
                <ArrowUpCircle className="h-4 w-4" /> 重新上架
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-3 gap-5">
        {/* ── 左栏：图片管理 ── */}
        <div className="col-span-1">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-slate-700">商品图片 ({images.length}/8)</h3>
              <button onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2.5 py-1.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100">
                <Upload className="h-3 w-3" /> 上传
              </button>
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />
            </div>
            {images.length === 0 ? (
              <div className="flex h-40 items-center justify-center rounded-md border-2 border-dashed border-slate-200 text-slate-300">
                <Package className="h-10 w-10" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {images.map((img) => (
                  <div key={img.id} className="group relative">
                    <img src={img.full_url} alt="" className="h-24 w-full rounded border border-slate-200 object-cover" />
                    {img.image_type === "MAIN" && <span className="absolute left-1 top-1 rounded bg-blue-600 px-1 py-0.5 text-[9px] text-white">主图</span>}
                    {img.sku_id && <span className="absolute left-1 bottom-1 rounded bg-slate-600 px-1 py-0.5 text-[9px] text-white">SKU</span>}
                    <button onClick={() => handleDeleteImage(img.id)} className="absolute right-1 top-1 hidden rounded bg-red-500/80 p-0.5 text-white group-hover:block">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── 右栏：SPU 信息 + Tab ── */}
        <div className="col-span-2 space-y-4">
          {/* SPU 基础信息卡 */}
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="grid grid-cols-3 gap-4 text-[13px]">
              <div><span className="text-slate-500">SPU 编码</span><p className="mt-0.5 font-mono font-semibold text-slate-900">{p.spu_code}</p></div>
              <div><span className="text-slate-500">产地 / Origin</span><p className="mt-0.5 font-medium text-slate-900">{p.origin}</p></div>
              <div><span className="text-slate-500">品牌 / Brand</span><p className="mt-0.5 font-medium text-slate-900">{p.brand || "—"}</p></div>
              <div><span className="text-slate-500">HS 编码</span><p className="mt-0.5 font-mono font-medium text-slate-900">{p.hs_code || "—"}</p></div>
              <div><span className="text-slate-500">品类</span><p className="mt-0.5 font-medium text-slate-900">{p.category_code}</p></div>
              <div><span className="text-slate-500">SKU 数量</span><p className="mt-0.5 font-semibold text-slate-900">{allSkus.length}</p></div>
              {p.certifications && p.certifications.length > 0 && (
                <div className="col-span-3">
                  <span className="text-slate-500">认证 / Certifications</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {p.certifications.map((c: string) => (
                      <span key={c} className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {p.selling_points && (
                <div className="col-span-3">
                  <span className="text-slate-500">卖点 / Selling Points</span>
                  <p className="mt-0.5 text-slate-700">{p.selling_points}</p>
                </div>
              )}
            </div>
          </div>

          {/* Tab 区 */}
          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="flex border-b border-slate-200">
              {([
                { key: "skus", label: `SKU 变体 (${allSkus.length})` },
                { key: "attrs", label: "品类属性 / Attributes" },
                { key: "desc", label: "商品描述 / Description" },
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-5 py-3 text-[13px] font-medium transition-colors ${
                    activeTab === tab.key ? "border-b-2 border-blue-600 text-blue-600" : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-5">
              {/* SKU 变体表格 */}
              {activeTab === "skus" && (
                <div className="space-y-3">
                  {/* 搜索栏 */}
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        placeholder="搜索 SKU 编码 / 名称 / 颜色 / 材质..."
                        className="w-full rounded-md border border-slate-200 py-2 pl-9 pr-3 text-[13px] focus:border-blue-400 focus:outline-none"
                        value={skuSearch}
                        onChange={(e) => { setSkuSearch(e.target.value); setSkuPage(1); }}
                      />
                    </div>
                    <span className="text-[12px] text-slate-400">{filteredSkus.length} 条</span>
                  </div>

                  {/* SKU 表格 */}
                  {pagedSkus.length === 0 ? (
                    <p className="py-8 text-center text-[13px] text-slate-400">暂无 SKU 变体</p>
                  ) : (
                    <table className="w-full text-[13px]">
                      <thead>
                        <tr className="border-b border-slate-200 text-left">
                          <th className="w-6 pb-2"></th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600">SKU 编码</th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600">规格</th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600">展示价</th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600">MOQ</th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600">状态</th>
                          <th className="pb-2 text-[12px] font-semibold text-slate-600 text-right">供货</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pagedSkus.map((sku) => (
                          <SkuRow
                            key={sku.id}
                            sku={sku}
                            productId={productId}
                            expanded={expandedSkuId === sku.id}
                            onToggle={() => setExpandedSkuId(expandedSkuId === sku.id ? null : sku.id)}
                            supplierFormSkuId={supplierFormSkuId}
                            onShowSupplierForm={(id) => { resetSupplierForm(); setSupplierFormSkuId(id); }}
                            sf={sf}
                            setSf={setSf}
                            supplierQuery={supplierQuery}
                            onSupplierQueryChange={handleSupplierQueryChange}
                            supplierOptions={supplierOptions}
                            showSupplierDropdown={showSupplierDropdown}
                            onSelectSupplier={selectSupplier}
                            onAddSupplier={handleAddSupplier}
                            onRemoveSupplier={handleRemoveSupplier}
                            onCancelSupplierForm={resetSupplierForm}
                          />
                        ))}
                      </tbody>
                    </table>
                  )}

                  {/* SKU 分页 */}
                  {skuPages > 1 && (
                    <div className="flex items-center justify-between pt-2 text-[12px] text-slate-500">
                      <span>第 {skuPage}/{skuPages} 页，共 {filteredSkus.length} 条</span>
                      <div className="flex gap-1">
                        <button disabled={skuPage <= 1} onClick={() => setSkuPage(skuPage - 1)} className="rounded border px-2.5 py-1 hover:bg-slate-50 disabled:opacity-40">上一页</button>
                        <button disabled={skuPage >= skuPages} onClick={() => setSkuPage(skuPage + 1)} className="rounded border px-2.5 py-1 hover:bg-slate-50 disabled:opacity-40">下一页</button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 属性 */}
              {activeTab === "attrs" && (
                attrs.length === 0
                  ? <p className="text-[13px] text-slate-400">暂无品类属性</p>
                  : <div className="grid grid-cols-3 gap-3">{attrs.map((a) => (
                      <div key={a.attr_key} className="rounded-md bg-slate-50 px-3 py-2 text-[13px]">
                        <span className="text-slate-500">{a.attr_key}</span>
                        <p className="font-medium text-slate-900">{a.attr_value}{a.attr_unit ? ` ${a.attr_unit}` : ""}</p>
                      </div>
                    ))}</div>
              )}

              {/* 描述 */}
              {activeTab === "desc" && (
                <div className="prose prose-sm max-w-none text-slate-700">
                  {p.description || <p className="text-slate-400">暂无描述</p>}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


// ── SKU 行组件（含展开区：阶梯价 + 供货关系）──────────────

interface SkuRowProps {
  sku: SkuOperator;
  productId: number;
  expanded: boolean;
  onToggle: () => void;
  supplierFormSkuId: number | null;
  onShowSupplierForm: (skuId: number) => void;
  sf: any;
  setSf: any;
  supplierQuery: string;
  onSupplierQueryChange: (q: string) => void;
  supplierOptions: SupplierListItem[];
  showSupplierDropdown: boolean;
  onSelectSupplier: (s: SupplierListItem) => void;
  onAddSupplier: (skuId: number) => void;
  onRemoveSupplier: (skuId: number, psId: number) => void;
  onCancelSupplierForm: () => void;
}

function SkuRow({
  sku, productId, expanded, onToggle,
  supplierFormSkuId, onShowSupplierForm,
  sf, setSf,
  supplierQuery, onSupplierQueryChange,
  supplierOptions, showSupplierDropdown, onSelectSupplier,
  onAddSupplier, onRemoveSupplier, onCancelSupplierForm,
}: SkuRowProps) {
  const specs = [sku.color, sku.material, sku.manufacturer_model].filter(Boolean).join(" / ");
  const tiers = sku.price_tiers || [];
  const suppliers = sku.supplier_relations || [];

  return (
    <>
      {/* 主行 */}
      <tr className="border-b border-slate-100 cursor-pointer hover:bg-slate-50" onClick={onToggle}>
        <td className="py-2.5">
          {expanded ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
        </td>
        <td className="py-2.5">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[12px] font-medium text-slate-800">{sku.sku_code}</span>
            {sku.is_default && <span className="rounded bg-blue-100 px-1 py-0.5 text-[9px] font-medium text-blue-700">默认</span>}
          </div>
        </td>
        <td className="py-2.5 text-slate-600">{specs || "—"}</td>
        <td className="py-2.5">
          {sku.price_min != null && sku.price_max != null ? (
            <span className="font-medium text-slate-800">{sku.currency} {Number(sku.price_min).toFixed(2)} - {Number(sku.price_max).toFixed(2)}</span>
          ) : (
            <span className="text-slate-400">未设价</span>
          )}
        </td>
        <td className="py-2.5 text-slate-600">{sku.moq} {sku.unit}</td>
        <td className="py-2.5"><StatusBadge status={sku.status} /></td>
        <td className="py-2.5 text-right">
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">{suppliers.length}</span>
        </td>
      </tr>

      {/* 展开区 */}
      {expanded && (
        <tr>
          <td colSpan={7} className="bg-slate-50/50 px-6 py-4">
            <div className="space-y-4">
              {/* 阶梯价 */}
              <div>
                <h4 className="mb-2 text-[12px] font-semibold text-slate-600">阶梯价 / Price Tiers</h4>
                {tiers.length === 0 ? (
                  <p className="text-[12px] text-slate-400">暂无阶梯价</p>
                ) : (
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-left text-slate-500">
                        <th className="pb-1.5 font-medium">数量区间</th>
                        <th className="pb-1.5 font-medium">单价</th>
                        <th className="pb-1.5 font-medium">标签</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tiers.map((t: SkuPriceTier) => (
                        <tr key={t.id} className="border-t border-slate-200">
                          <td className="py-1.5">{t.min_qty}{t.max_qty != null ? ` - ${t.max_qty}` : "+"}</td>
                          <td className="py-1.5 font-mono font-medium">{t.currency} {Number(t.unit_price).toFixed(2)}</td>
                          <td className="py-1.5 text-slate-400">{t.label || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* 供货关系 */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-[12px] font-semibold text-slate-600">供货关系 / Suppliers ({suppliers.length})</h4>
                  <button
                    onClick={(e) => { e.stopPropagation(); onShowSupplierForm(sku.id); }}
                    className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100"
                  >
                    <Plus className="h-3 w-3" /> 添加
                  </button>
                </div>

                {/* 添加供应商表单 */}
                {supplierFormSkuId === sku.id && (
                  <div className="mb-3 rounded-md border border-blue-200 bg-blue-50/50 p-3 space-y-2.5">
                    <div className="relative">
                      <label className="mb-1 block text-[11px] font-medium text-slate-600">供应商 / Supplier *</label>
                      <input
                        type="text" placeholder="输入名称搜索..."
                        className="w-full rounded border px-3 py-1.5 text-[12px]"
                        value={supplierQuery}
                        onChange={(e) => onSupplierQueryChange(e.target.value)}
                        onFocus={() => { if (supplierOptions.length > 0 && supplierQuery.length >= 1) onSupplierQueryChange(supplierQuery); }}
                        onBlur={() => setTimeout(() => {}, 200)}
                      />
                      {sf.supplier_org_id > 0 && (
                        <span className="absolute right-3 top-[26px] text-[11px] text-emerald-600">✓ {sf.supplier_org_name}</span>
                      )}
                      {showSupplierDropdown && supplierOptions.length > 0 && (
                        <div className="absolute z-10 mt-1 max-h-40 w-full overflow-auto rounded border border-slate-200 bg-white shadow-lg">
                          {supplierOptions.map((s) => (
                            <button key={s.id} type="button" className="flex w-full items-center justify-between px-3 py-2 text-left text-[12px] hover:bg-blue-50" onMouseDown={() => onSelectSupplier(s)}>
                              <span className="font-medium text-slate-800">{s.name}</span>
                              <span className="text-[11px] text-slate-400">{s.country_code}{s.grade ? ` · ${s.grade}` : ""}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="grid grid-cols-4 gap-2 text-[11px]">
                      <div><label className="mb-0.5 block font-medium text-slate-500">底价</label><input type="number" step="0.01" placeholder="选填" className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.supplier_price} onChange={(e) => setSf((f: any) => ({ ...f, supplier_price: e.target.value }))} /></div>
                      <div><label className="mb-0.5 block font-medium text-slate-500">币种</label>
                        <select className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.supplier_currency} onChange={(e) => setSf((f: any) => ({ ...f, supplier_currency: e.target.value }))}>
                          <option value="CNY">CNY</option><option value="USD">USD</option><option value="TZS">TZS</option>
                        </select>
                      </div>
                      <div><label className="mb-0.5 block font-medium text-slate-500">CIF (USD)</label><input type="number" step="0.01" placeholder="选填" className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.cif_price_usd} onChange={(e) => setSf((f: any) => ({ ...f, cif_price_usd: e.target.value }))} /></div>
                      <div><label className="mb-0.5 block font-medium text-slate-500">PVoC</label>
                        <select className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.pvoc_status} onChange={(e) => setSf((f: any) => ({ ...f, pvoc_status: e.target.value }))}>
                          <option value="">未设</option><option value="OBTAINED">已获得</option><option value="CAN_ARRANGE">可安排</option><option value="UNAVAILABLE">不可用</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-[11px]">
                      <label className="flex items-center gap-1"><input type="checkbox" checked={sf.has_coc} onChange={(e) => setSf((f: any) => ({ ...f, has_coc: e.target.checked }))} /> CoC</label>
                      <label className="flex items-center gap-1"><input type="checkbox" checked={sf.is_preferred} onChange={(e) => setSf((f: any) => ({ ...f, is_preferred: e.target.checked }))} /> 优选</label>
                      <div className="flex-1" />
                      <button onClick={onCancelSupplierForm} className="rounded border px-3 py-1 text-slate-600 hover:bg-slate-50">取消</button>
                      <button onClick={() => onAddSupplier(sku.id)} disabled={!sf.supplier_org_id} className="rounded bg-blue-600 px-3 py-1 font-medium text-white hover:bg-blue-700 disabled:opacity-40">保存</button>
                    </div>
                  </div>
                )}

                {suppliers.length === 0 ? (
                  <p className="text-[12px] text-slate-400">暂无供货关系</p>
                ) : (
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-left text-slate-500">
                        <th className="pb-1.5 font-medium">供应商</th>
                        <th className="pb-1.5 font-medium">底价</th>
                        <th className="pb-1.5 font-medium">CIF</th>
                        <th className="pb-1.5 font-medium">PVoC</th>
                        <th className="pb-1.5 font-medium text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {suppliers.map((s: SupplierRelationDetail) => (
                        <tr key={s.id} className="border-t border-slate-200">
                          <td className="py-1.5">
                            <div className="flex items-center gap-1">
                              {s.is_preferred && <Star className="h-3 w-3 fill-amber-400 text-amber-400" />}
                              <span className="font-medium">{s.supplier_org_name || `#${s.supplier_org_id}`}</span>
                            </div>
                          </td>
                          <td className="py-1.5 font-mono">{s.supplier_currency} {Number(s.supplier_price).toFixed(2)}</td>
                          <td className="py-1.5 font-mono">{s.cif_price_usd != null ? `$${Number(s.cif_price_usd).toFixed(2)}` : "—"}</td>
                          <td className="py-1.5">
                            <div className="flex gap-1">
                              {s.pvoc_status && <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700">{s.pvoc_status}</span>}
                              {s.has_coc && <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">CoC</span>}
                            </div>
                          </td>
                          <td className="py-1.5 text-right">
                            <button onClick={() => onRemoveSupplier(sku.id, s.id)} className="rounded p-1 text-red-400 hover:bg-red-50">
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
