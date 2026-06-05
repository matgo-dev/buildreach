"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Package, ChevronLeft, ChevronRight, MessageCircle, Phone,
  CheckCircle, ShieldCheck, Truck, Clock, Home,
} from "lucide-react";

import { publicProductApi } from "@/lib/productApi";
import { MallHeader } from "@/components/mall/MallHeader";
import { MallFooter } from "@/components/mall/MallFooter";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8002";

export default function PublicProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = Number(params.id);

  const [product, setProduct] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(0);
  const [activeTab, setActiveTab] = useState<"specs" | "desc">("specs");

  useEffect(() => {
    publicProductApi.detail(productId).then(setProduct).catch(console.error).finally(() => setLoading(false));
  }, [productId]);

  if (loading) return <div className="min-h-screen bg-[#F5F5F5]"><MallHeader /><div className="flex h-96 items-center justify-center text-slate-400">加载中...</div></div>;
  if (!product) return <div className="min-h-screen bg-[#F5F5F5]"><MallHeader /><div className="flex h-96 items-center justify-center text-slate-400">商品不存在 / Product not found</div></div>;

  const p = product;
  const images = p.images || [];
  const attrs = p.attributes || [];
  const tzsPrice = (Number(p.price_min) * 2500).toLocaleString();

  return (
    <div className="min-h-screen bg-[#F5F5F5]">
      <MallHeader />

      {/* 面包屑 */}
      <div className="mx-auto max-w-[1280px] px-4 py-2 text-[12px] text-slate-500 flex items-center gap-1">
        <Home className="h-3 w-3" />
        <span className="cursor-pointer hover:text-slate-700" onClick={() => router.push("/products")}>商品列表</span>
        <ChevronRight className="h-3 w-3" />
        <span className="text-slate-800 font-medium line-clamp-1">{p.name}</span>
      </div>

      <div className="mx-auto max-w-[1280px] px-4 pb-8">
        {/* 商品主区域 */}
        <div className="rounded border border-slate-200 bg-white p-6">
          <div className="flex gap-8">
            {/* 左：图片 */}
            <div className="w-[400px] shrink-0">
              <div className="relative aspect-square overflow-hidden rounded border border-slate-200 bg-[#FAFAFA]">
                {images.length > 0 ? (
                  <>
                    <img src={images[selectedImage]?.full_url} alt={p.name} className="h-full w-full object-contain p-6" />
                    {images.length > 1 && (
                      <>
                        <button onClick={() => setSelectedImage((i) => (i > 0 ? i - 1 : images.length - 1))} className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-1.5 shadow hover:bg-white"><ChevronLeft className="h-4 w-4 text-slate-700" /></button>
                        <button onClick={() => setSelectedImage((i) => (i < images.length - 1 ? i + 1 : 0))} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-1.5 shadow hover:bg-white"><ChevronRight className="h-4 w-4 text-slate-700" /></button>
                      </>
                    )}
                  </>
                ) : (
                  <div className="flex h-full items-center justify-center"><Package className="h-20 w-20 text-slate-200" /></div>
                )}
              </div>
              {images.length > 1 && (
                <div className="mt-3 flex gap-2">
                  {images.map((img: any, idx: number) => (
                    <button key={img.id} onClick={() => setSelectedImage(idx)} className={`h-16 w-16 overflow-hidden rounded border-2 ${idx === selectedImage ? "border-[#0D4D4D]" : "border-slate-200"}`}>
                      <img src={img.full_url} alt="" className="h-full w-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 右：商品信息 */}
            <div className="flex-1 space-y-5">
              <div>
                <h1 className="text-[22px] font-bold text-slate-900">{p.name}</h1>
                <p className="mt-1 text-[13px] text-slate-400">SKU: {p.sku_code} · 品类: {p.category_code}</p>
              </div>

              {/* 认证标签 */}
              {p.certifications && p.certifications.length > 0 && (
                <div className="flex items-center gap-2">
                  {p.certifications.map((c: string) => (
                    <span key={c} className="rounded border border-[#0D4D4D]/20 bg-[#0D4D4D]/5 px-2.5 py-1 text-[11px] font-medium text-[#0D4D4D]">
                      <ShieldCheck className="mr-1 inline h-3 w-3" />{c}
                    </span>
                  ))}
                </div>
              )}

              {/* 价格区 */}
              <div className="rounded-lg bg-[#F0FAF8] border border-[#0D4D4D]/10 p-4">
                <div className="flex items-baseline gap-3">
                  <span className="text-[28px] font-bold text-[#0D4D4D]">TZS {tzsPrice}</span>
                  <span className="text-[14px] text-slate-500">~ TZS {(Number(p.price_max) * 2500).toLocaleString()}</span>
                  <span className="text-[13px] text-slate-400">/ {p.unit}</span>
                </div>
                <p className="mt-1 text-[12px] text-slate-400">
                  (≈ ${Number(p.price_min).toFixed(2)} - ${Number(p.price_max).toFixed(2)} USD)
                </p>
              </div>

              {/* 关键参数 */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "起订量 / MOQ", value: `${p.moq} ${p.unit}`, icon: <Package className="h-4 w-4 text-[#0D4D4D]" /> },
                  { label: "交期 / Lead Time", value: `${p.lead_time_days ?? "—"} 天`, icon: <Clock className="h-4 w-4 text-[#0D4D4D]" /> },
                  { label: "产地 / Origin", value: p.origin, icon: <Truck className="h-4 w-4 text-[#0D4D4D]" /> },
                  { label: "品牌 / Brand", value: p.brand || "OEM", icon: <CheckCircle className="h-4 w-4 text-[#0D4D4D]" /> },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3 rounded border border-slate-200 p-3">
                    {item.icon}
                    <div>
                      <span className="block text-[11px] text-slate-400">{item.label}</span>
                      <span className="block text-[14px] font-semibold text-slate-900">{item.value}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* 库存状态 */}
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-[12px] font-medium text-emerald-600">
                  ● 有货 / In Stock
                </span>
              </div>

              {/* 操作按钮 */}
              <div className="flex items-center gap-3 pt-2">
                <button className="flex-1 rounded-lg bg-[#0D4D4D] py-3 text-center text-[14px] font-semibold text-white hover:bg-[#1A6B6B] transition-colors">
                  询价报价 / Request Quote
                </button>
                <button className="rounded-lg bg-[#25D366] px-6 py-3 text-[14px] font-semibold text-white hover:bg-[#20BD5A] transition-colors">
                  <MessageCircle className="mr-1.5 inline h-4 w-4" />WhatsApp
                </button>
              </div>
              <p className="text-center text-[11px] text-slate-400">平台运营团队将在 24 小时内回复 / Response within 24h</p>
            </div>
          </div>
        </div>

        {/* 规格参数 + 描述 */}
        {(attrs.length > 0 || p.description) && (
          <div className="mt-5 rounded border border-slate-200 bg-white">
            {/* Tab 头 */}
            <div className="flex border-b border-slate-200 px-6">
              <button
                onClick={() => setActiveTab("specs")}
                className={`px-4 py-3 text-[13px] font-medium transition-colors ${activeTab === "specs" ? "border-b-2 border-[#0D4D4D] text-[#0D4D4D]" : "text-slate-500 hover:text-slate-700"}`}
              >
                规格参数 / Specifications
              </button>
              {p.description && (
                <button
                  onClick={() => setActiveTab("desc")}
                  className={`px-4 py-3 text-[13px] font-medium transition-colors ${activeTab === "desc" ? "border-b-2 border-[#0D4D4D] text-[#0D4D4D]" : "text-slate-500 hover:text-slate-700"}`}
                >
                  商品描述 / Description
                </button>
              )}
            </div>

            <div className="p-6">
              {activeTab === "specs" && (
                attrs.length > 0 ? (
                  <table className="w-full text-[13px]">
                    <tbody>
                      {attrs.map((a: any, idx: number) => (
                        <tr key={a.attr_key} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="w-[200px] px-4 py-2.5 font-medium text-slate-600">{a.attr_key}</td>
                          <td className="px-4 py-2.5 text-slate-900">{a.attr_value}{a.attr_unit ? ` ${a.attr_unit}` : ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-[13px] text-slate-400">暂无规格参数</p>
                )
              )}
              {activeTab === "desc" && p.description && (
                <div className="prose prose-sm max-w-none text-slate-700">{p.description}</div>
              )}
            </div>
          </div>
        )}
      </div>

      <MallFooter />
    </div>
  );
}
