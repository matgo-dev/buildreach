"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowUpCircle, ArrowDownCircle, Trash2, Upload, Plus, Package, Star,
} from "lucide-react";

import {
  operatorProductApi,
  type ProductOperatorDetail,
  type ProductSupplierDetail,
} from "@/lib/productApi";
import { suppliersApi, type SupplierListItem } from "@/lib/api/suppliers";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { StatusBadge } from "@/components/products/StatusBadge";

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = Number(params.id);
  const fileRef = useRef<HTMLInputElement>(null);

  const [product, setProduct] = useState<ProductOperatorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"attrs" | "suppliers" | "desc">("attrs");

  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [sf, setSf] = useState({
    supplier_org_id: 0, supplier_org_name: "", supplier_price: "", supplier_moq: "",
    supplier_lead_time_days: "", has_pvoc: false, has_coc: false,
    is_preferred: false, notes: "",
  });

  // 供应商搜索
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

  const handleAddSupplier = async () => {
    if (!sf.supplier_org_id) { alert("请选择供应商"); return; }
    try {
      await operatorProductApi.addSupplier(productId, {
        supplier_org_id: sf.supplier_org_id,
        supplier_price: sf.supplier_price ? parseFloat(sf.supplier_price) : 0,
        supplier_moq: sf.supplier_moq ? parseInt(sf.supplier_moq) : null,
        supplier_lead_time_days: sf.supplier_lead_time_days ? parseInt(sf.supplier_lead_time_days) : null,
        has_pvoc: sf.has_pvoc, has_coc: sf.has_coc, is_preferred: sf.is_preferred,
      });
      setShowSupplierForm(false);
      setSf({ supplier_org_id: 0, supplier_org_name: "", supplier_price: "", supplier_moq: "", supplier_lead_time_days: "", has_pvoc: false, has_coc: false, is_preferred: false, notes: "" });
      setSupplierQuery("");
      fetchProduct();
    } catch (err: any) { alert(err.message || "添加失败"); }
  };

  const handleRemoveSupplier = async (psId: number) => {
    if (!confirm("确定移除该供应商？")) return;
    try { await operatorProductApi.removeSupplier(productId, psId); fetchProduct(); }
    catch (err: any) { alert(err.message || "移除失败"); }
  };

  if (loading) return <div className="flex h-64 items-center justify-center text-slate-400">加载中...</div>;
  if (!product) return <div className="flex h-64 items-center justify-center text-slate-400">商品不存在</div>;

  const p = product;
  const images = p.images || [];
  const attrs = p.attributes || [];
  const suppliers = p.suppliers || [];

  return (
    <div className="space-y-5">
      {/* 页面头 */}
      <AdminPageHeader
        titleZh={p.name}
        titleEn={p.name_i18n ? Object.values(p.name_i18n).filter(Boolean).join(" / ") : p.sku_code}
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
                    {img.sort_order === 0 && <span className="absolute left-1 top-1 rounded bg-blue-600 px-1 py-0.5 text-[9px] text-white">主图</span>}
                    <button onClick={() => handleDeleteImage(img.id)} className="absolute right-1 top-1 hidden rounded bg-red-500/80 p-0.5 text-white group-hover:block">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── 右栏：信息 + Tab ── */}
        <div className="col-span-2 space-y-4">
          {/* 基础信息卡 */}
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="grid grid-cols-3 gap-4 text-[13px]">
              <div><span className="text-slate-500">价格区间 / Price</span><p className="mt-0.5 font-semibold text-slate-900">${Number(p.price_min).toFixed(2)} - ${Number(p.price_max).toFixed(2)} {p.currency}</p></div>
              <div><span className="text-slate-500">起订量 / MOQ</span><p className="mt-0.5 font-semibold text-slate-900">{p.moq} {p.unit}</p></div>
              <div><span className="text-slate-500">交期 / Lead Time</span><p className="mt-0.5 font-semibold text-slate-900">{p.lead_time_days ?? "—"} 天</p></div>
              <div><span className="text-slate-500">产地 / Origin</span><p className="mt-0.5 font-medium text-slate-900">{p.origin}</p></div>
              <div><span className="text-slate-500">品牌 / Brand</span><p className="mt-0.5 font-medium text-slate-900">{p.brand || "—"}</p></div>
              <div><span className="text-slate-500">HS 编码</span><p className="mt-0.5 font-mono font-medium text-slate-900">{p.hs_code || "—"}</p></div>
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
            </div>
          </div>

          {/* Tab 区 */}
          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="flex border-b border-slate-200">
              {([
                { key: "attrs", label: "品类属性 / Attributes" },
                { key: "suppliers", label: `供货关系 / Suppliers (${suppliers.length})` },
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

              {/* 供货关系 */}
              {activeTab === "suppliers" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-[13px] font-medium text-slate-700">供货关系管理</h4>
                    <button onClick={() => setShowSupplierForm(true)} className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-3 py-1.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100">
                      <Plus className="h-3 w-3" /> 添加供应商
                    </button>
                  </div>

                  {showSupplierForm && (
                    <div className="rounded-md border border-blue-200 bg-blue-50/50 p-4 space-y-3">
                      {/* 第一行：供应商搜索（必选） */}
                      <div className="relative">
                        <label className="mb-1 block text-[11px] font-medium text-slate-600">供应商 / Supplier *</label>
                        <input
                          type="text"
                          placeholder="输入名称搜索..."
                          className="w-full rounded border px-3 py-2 text-[13px]"
                          value={supplierQuery}
                          onChange={(e) => handleSupplierQueryChange(e.target.value)}
                          onFocus={() => { if (supplierOptions.length > 0) setShowSupplierDropdown(true); }}
                          onBlur={() => setTimeout(() => setShowSupplierDropdown(false), 200)}
                        />
                        {sf.supplier_org_id > 0 && (
                          <span className="absolute right-3 top-[30px] text-[11px] text-emerald-600">✓ {sf.supplier_org_name}</span>
                        )}
                        {showSupplierDropdown && supplierOptions.length > 0 && (
                          <div className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-slate-200 bg-white shadow-lg">
                            {supplierOptions.map((s) => (
                              <button
                                key={s.id}
                                type="button"
                                className="flex w-full items-center justify-between px-3 py-2.5 text-left text-[13px] hover:bg-blue-50"
                                onMouseDown={() => selectSupplier(s)}
                              >
                                <span className="font-medium text-slate-800">{s.name}</span>
                                <span className="text-[11px] text-slate-400">{s.country_code}{s.grade ? ` · ${s.grade}` : ""}</span>
                              </button>
                            ))}
                          </div>
                        )}
                        {showSupplierDropdown && supplierOptions.length === 0 && supplierQuery.length >= 1 && (
                          <div className="absolute z-10 mt-1 w-full rounded border border-slate-200 bg-white px-3 py-2.5 text-[13px] text-slate-400 shadow-lg">
                            未找到匹配的供应商
                          </div>
                        )}
                      </div>
                      {/* 第二行：供货条件（全部选填） */}
                      <div className="grid grid-cols-4 gap-3 text-[12px]">
                        <div><label className="mb-1 block text-[11px] font-medium text-slate-500">底价 / Price</label><input type="number" step="0.01" placeholder="选填" className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.supplier_price} onChange={(e) => setSf((f) => ({ ...f, supplier_price: e.target.value }))} /></div>
                        <div><label className="mb-1 block text-[11px] font-medium text-slate-500">起订量 / MOQ</label><input type="number" placeholder="选填" className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.supplier_moq} onChange={(e) => setSf((f) => ({ ...f, supplier_moq: e.target.value }))} /></div>
                        <div><label className="mb-1 block text-[11px] font-medium text-slate-500">交期 / Lead Time (天)</label><input type="number" placeholder="选填" className="w-full rounded border px-2 py-1.5 text-[12px]" value={sf.supplier_lead_time_days} onChange={(e) => setSf((f) => ({ ...f, supplier_lead_time_days: e.target.value }))} /></div>
                        <div className="flex items-end gap-3">
                          <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={sf.has_pvoc} onChange={(e) => setSf((f) => ({ ...f, has_pvoc: e.target.checked }))} /> PVoC</label>
                          <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={sf.has_coc} onChange={(e) => setSf((f) => ({ ...f, has_coc: e.target.checked }))} /> CoC</label>
                          <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" checked={sf.is_preferred} onChange={(e) => setSf((f) => ({ ...f, is_preferred: e.target.checked }))} /> 优选</label>
                        </div>
                      </div>
                      {/* 操作按钮 */}
                      <div className="flex justify-end gap-2">
                        <button onClick={() => { setShowSupplierForm(false); setSupplierQuery(""); }} className="rounded border px-4 py-1.5 text-[12px] text-slate-600 hover:bg-slate-50">取消</button>
                        <button onClick={handleAddSupplier} disabled={!sf.supplier_org_id} className="rounded bg-blue-600 px-4 py-1.5 text-[12px] font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed">保存</button>
                      </div>
                    </div>
                  )}

                  {suppliers.length === 0
                    ? <p className="text-[13px] text-slate-400">暂无供货关系</p>
                    : (
                      <table className="w-full text-[13px]">
                        <thead>
                          <tr className="border-b border-slate-200 text-left">
                            <th className="pb-2 text-[12px] font-semibold text-slate-600">供应商 / Supplier</th>
                            <th className="pb-2 text-[12px] font-semibold text-slate-600">底价</th>
                            <th className="pb-2 text-[12px] font-semibold text-slate-600">起订量</th>
                            <th className="pb-2 text-[12px] font-semibold text-slate-600">交期</th>
                            <th className="pb-2 text-[12px] font-semibold text-slate-600">认证</th>
                            <th className="pb-2 text-[12px] font-semibold text-slate-600 text-right">操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          {suppliers.map((s: ProductSupplierDetail) => (
                            <tr key={s.id} className="border-b border-slate-100">
                              <td className="py-2.5"><div className="flex items-center gap-1">{s.is_preferred && <Star className="h-3 w-3 fill-amber-400 text-amber-400" />}<span className="font-medium">{s.supplier_org_name || `#${s.supplier_org_id}`}</span></div></td>
                              <td className="py-2.5 font-mono">${Number(s.supplier_price).toFixed(2)}</td>
                              <td className="py-2.5">{s.supplier_moq ?? "—"}</td>
                              <td className="py-2.5">{s.supplier_lead_time_days ?? "—"} 天</td>
                              <td className="py-2.5"><div className="flex gap-1">{s.has_pvoc && <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700">PVoC</span>}{s.has_coc && <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">CoC</span>}</div></td>
                              <td className="py-2.5 text-right"><button onClick={() => handleRemoveSupplier(s.id)} className="rounded p-1 text-red-400 hover:bg-red-50"><Trash2 className="h-3.5 w-3.5" /></button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  }
                </div>
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
