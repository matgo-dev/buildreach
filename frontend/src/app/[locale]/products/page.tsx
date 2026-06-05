"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Package, Grid3x3, List, CheckCircle, Home, ChevronRight,
  MessageCircle, Phone,
} from "lucide-react";

import { publicProductApi, type ProductPublic, type PageResult } from "@/lib/productApi";
import { api } from "@/lib/api";
import { MallHeader } from "@/components/mall/MallHeader";
import { MallFooter } from "@/components/mall/MallFooter";
import { CategorySidebar, getCategoryLabel, type CategoryItem } from "@/components/mall/CategorySidebar";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8002";
const PAGE_SIZE = 14;

export default function PublicProductsPage() {
  const router = useRouter();
  const [data, setData] = useState<PageResult<ProductPublic> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [categoryCode, setCategoryCode] = useState("");
  const [sort, setSort] = useState("newest");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [categories, setCategories] = useState<CategoryItem[]>([]);

  useEffect(() => {
    api.get<CategoryItem[]>("/api/v1/categories?level=1&is_active=true").then(setCategories).catch(console.error);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await publicProductApi.list({
        category_code: categoryCode || undefined,
        keyword: keyword || undefined,
        sort, page, size: PAGE_SIZE,
      });
      setData(res);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [categoryCode, keyword, sort, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const activeCat = categories.find((c) => c.code === categoryCode);

  return (
    <div className="min-h-screen bg-[#F5F5F5]">
      <MallHeader keyword={keyword} onKeywordChange={(v) => { setKeyword(v); setPage(1); }} />

      {/* 面包屑 */}
      <div className="mx-auto max-w-[1280px] px-4 py-2 text-[12px] text-slate-500 flex items-center gap-1">
        <Home className="h-3 w-3" /><span>首页 / Home</span>
        <ChevronRight className="h-3 w-3" />
        <span className="text-slate-800 font-medium">
          {categoryCode ? getCategoryLabel(activeCat!).zh : "全品类采购 / All Categories"}
        </span>
      </div>

      <div className="mx-auto max-w-[1280px] px-4 pb-8">
        <div className="flex gap-5">
          {/* 左栏 */}
          <CategorySidebar
            categories={categories}
            activeCode={categoryCode}
            onSelect={(code) => { setCategoryCode(code); setPage(1); }}
          />

          {/* 中栏 */}
          <main className="flex-1 min-w-0">
            {/* Banner */}
            <div className="mb-4 flex gap-4">
              <div className="flex-1 rounded border border-slate-200 bg-white p-5">
                <h1 className="text-[20px] font-bold text-slate-900">
                  {categoryCode ? getCategoryLabel(activeCat!).zh : "全品类采购"}
                  <span className="ml-2 text-[14px] font-normal text-slate-400">
                    / {categoryCode ? getCategoryLabel(activeCat!).en : "All Categories"}
                  </span>
                </h1>
                <p className="mt-1 text-[12px] text-slate-500">一站采购，覆盖建筑全产业链 · One-stop sourcing for the complete building ecosystem in Tanzania</p>
                <div className="mt-4 flex items-center gap-8">
                  {[
                    { num: "16+", zh: "主类目" }, { num: "2,000+", zh: "品牌" },
                    { num: "200,000+", zh: "SKU" }, { num: "100+", zh: "本地门店服务" },
                  ].map((s) => (
                    <div key={s.zh}><span className="text-[20px] font-bold text-[#0D4D4D]">{s.num}</span><p className="text-[10px] text-slate-400">{s.zh}</p></div>
                  ))}
                </div>
              </div>
              <div className="w-[320px] shrink-0 rounded overflow-hidden relative bg-[#0D4D4D]">
                <div className="absolute inset-0 bg-gradient-to-r from-[#0D4D4D]/80 to-transparent z-10" />
                <div className="absolute bottom-0 left-0 right-0 z-20 p-4 text-white">
                  <p className="text-[15px] font-bold">服务达累斯萨拉姆 100+ 本地门店</p>
                  <p className="text-[11px] text-white/80 mt-0.5">Serving 100+ Local Stores Around Dar es Salaam</p>
                </div>
                <img src="https://images.unsplash.com/photo-1578575437130-527eed3abbec?w=640&q=80" alt="port" className="h-full w-full object-cover opacity-60" />
              </div>
            </div>

            {/* 筛选条 */}
            <div className="mb-3 rounded border border-slate-200 bg-white px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="font-medium text-slate-800">筛选 / Filters</span>
                <select className="rounded border border-slate-200 px-2 py-1.5 text-slate-600 bg-white"><option>品牌 / Brand</option></select>
                <select className="rounded border border-slate-200 px-2 py-1.5 text-slate-600 bg-white"><option>MOQ / 最小起订量</option></select>
                <select className="rounded border border-slate-200 px-2 py-1.5 text-slate-600 bg-white"><option>交期 / Delivery Time</option></select>
                <select className="rounded border border-slate-200 px-2 py-1.5 text-slate-600 bg-white"><option>认证 / Certification</option></select>
                <label className="flex items-center gap-1 text-[11px] ml-2"><input type="checkbox" className="h-3 w-3 rounded" />有货 / In Stock</label>
                <label className="flex items-center gap-1 text-[11px]"><input type="checkbox" className="h-3 w-3 rounded" />合规进口</label>
              </div>
            </div>

            {/* 结果条 */}
            <div className="mb-3 flex items-center justify-between text-[12px]">
              <span className="text-slate-600 font-medium">{total.toLocaleString()} Products / 个产品</span>
              <div className="flex items-center gap-3">
                <span className="text-slate-400">排序:</span>
                <select className="rounded border border-slate-200 bg-white px-2 py-1 text-[12px]" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
                  <option value="newest">最新 / Newest</option>
                  <option value="price_asc">价格从低到高</option>
                  <option value="price_desc">价格从高到低</option>
                </select>
                <div className="flex items-center gap-0.5 border border-slate-200 rounded overflow-hidden">
                  <button onClick={() => setViewMode("grid")} className={`p-1.5 ${viewMode === "grid" ? "bg-[#0D4D4D] text-white" : "bg-white text-slate-400"}`}><Grid3x3 className="h-3.5 w-3.5" /></button>
                  <button onClick={() => setViewMode("list")} className={`p-1.5 ${viewMode === "list" ? "bg-[#0D4D4D] text-white" : "bg-white text-slate-400"}`}><List className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            </div>

            {/* 商品网格 */}
            {loading ? (
              <div className="flex h-48 items-center justify-center text-slate-400 text-[13px]">加载中...</div>
            ) : items.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded border border-dashed border-slate-300 bg-white text-slate-400">
                <Package className="mb-3 h-14 w-14" />
                <p className="text-[15px] font-medium">暂无商品</p>
                <p className="mt-1 text-[12px]">该品类下还没有上架商品 / No products found</p>
              </div>
            ) : (
              <div className={viewMode === "grid" ? "grid grid-cols-7 gap-3" : "space-y-2"}>
                {items.map((p) => viewMode === "grid" ? (
                  <div key={p.id} onClick={() => router.push(`/products/${p.id}`)} className="group cursor-pointer rounded border border-slate-200 bg-white transition-all hover:shadow-md hover:-translate-y-0.5">
                    <div className="aspect-square overflow-hidden bg-[#FAFAFA] rounded-t">
                      {p.main_image ? <img src={`${API_BASE}${p.main_image}`} alt={p.name} className="h-full w-full object-contain p-2 transition-transform group-hover:scale-105" /> : <div className="flex h-full items-center justify-center"><Package className="h-8 w-8 text-slate-200" /></div>}
                    </div>
                    <div className="p-2">
                      <h3 className="text-[12px] font-medium text-slate-900 line-clamp-1">{p.name}</h3>
                      {p.brand && <p className="text-[10px] text-slate-400 mt-0.5">{p.brand}</p>}
                      <p className="mt-1.5 text-[13px] font-bold text-[#0D4D4D]">TZS {(Number(p.price_min) * 2500).toLocaleString()} <span className="text-[10px] font-normal text-slate-400">/ {p.unit}</span></p>
                      <span className="mt-1 inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1 py-0.5 text-[9px] text-emerald-600">● 有货 / In Stock</span>
                      <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-400">
                        <span>MOQ {p.moq} {p.unit}</span>
                        <span>交期 {p.lead_time_days ?? "—"} 天</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div key={p.id} onClick={() => router.push(`/products/${p.id}`)} className="flex cursor-pointer gap-4 rounded border border-slate-200 bg-white p-3 hover:shadow-md">
                    <div className="h-20 w-20 shrink-0 rounded bg-[#FAFAFA] overflow-hidden">{p.main_image ? <img src={`${API_BASE}${p.main_image}`} alt="" className="h-full w-full object-contain p-1" /> : <div className="flex h-full items-center justify-center"><Package className="h-6 w-6 text-slate-200" /></div>}</div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-[13px] font-medium text-slate-900">{p.name}</h3>
                      <p className="mt-1 text-[14px] font-bold text-[#0D4D4D]">TZS {(Number(p.price_min) * 2500).toLocaleString()} / {p.unit}</p>
                      <div className="mt-1 flex items-center gap-3 text-[10px] text-slate-400"><span className="text-emerald-600">● 有货</span><span>MOQ {p.moq}</span><span>交期 {p.lead_time_days ?? "—"} 天</span></div>
                    </div>
                    <div className="flex items-center shrink-0"><button className="rounded bg-[#25D366] px-3 py-1.5 text-[11px] font-medium text-white hover:bg-[#20BD5A]">WhatsApp 询价</button></div>
                  </div>
                ))}
              </div>
            )}

            {data && data.pages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-2 text-[12px]">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border border-slate-200 bg-white px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40">上一页</button>
                {Array.from({ length: Math.min(data.pages, 7) }, (_, i) => i + 1).map((p) => (
                  <button key={p} onClick={() => setPage(p)} className={`rounded px-3 py-1.5 font-medium ${p === page ? "bg-[#0D4D4D] text-white" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>{p}</button>
                ))}
                <button disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)} className="rounded border border-slate-200 bg-white px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40">下一页</button>
              </div>
            )}
          </main>

          {/* 右栏 */}
          <aside className="w-[220px] shrink-0 space-y-3">
            <div className="rounded border border-slate-200 bg-white p-4">
              <h3 className="text-[14px] font-bold text-slate-900">门店入驻 / Merchant Onboarding</h3>
              <p className="mt-1 text-[11px] text-slate-500">加入东非建筑工业品平台，拓展业务</p>
              <ul className="mt-3 space-y-1.5 text-[11px] text-slate-600">
                <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-[#0D4D4D]" />免费入驻 / Free Registration</li>
                <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-[#0D4D4D]" />专属店铺 / Storefront</li>
                <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-[#0D4D4D]" />海量买家 / More Buyer Reach</li>
                <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-[#0D4D4D]" />营销工具 / Marketing Tools</li>
              </ul>
              <button className="mt-3 w-full rounded bg-[#0D4D4D] py-2 text-[12px] font-medium text-white hover:bg-[#1A6B6B]">立即入驻 / Join Now</button>
            </div>
            <div className="rounded border border-slate-200 bg-white p-4">
              <h3 className="text-[14px] font-bold text-slate-900">快速询盘 / WhatsApp Inquiry</h3>
              <p className="mt-1 text-[11px] text-slate-500">一键联系采购顾问，快速获取报价</p>
              <div className="mt-3 flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#25D366]/10"><MessageCircle className="h-5 w-5 text-[#25D366]" /></div>
                <div>
                  <div className="flex items-center gap-1 text-[12px]"><Phone className="h-3 w-3 text-slate-500" /><span className="font-bold text-slate-800">+255 697 123 456</span></div>
                  <p className="text-[10px] text-slate-400">Mon - Sat 8:00 - 18:00</p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <MallFooter />
    </div>
  );
}
