"use client";
import Link from "next/link";
import {
  ShoppingBag, Globe, Shield, Bot, ArrowRight, Building2,
  Truck, Zap, Package, Wrench,
  Flame, MoveUp, Columns3, Droplets, PaintBucket, Umbrella,
  type LucideIcon,
} from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";

const CATEGORIES: { code: string; name: string; icon: LucideIcon }[] = [
  { code: "ALU_PANEL",   name: "铝单板", icon: Columns3 },
  { code: "CURTAIN_WALL", name: "幕墙",  icon: Building2 },
  { code: "MEP",         name: "机电",   icon: Zap },
  { code: "STEEL",       name: "钢结构", icon: Wrench },
  { code: "PLUMBING",    name: "给排水", icon: Droplets },
  { code: "ELECTRICAL",  name: "电气",   icon: Zap },
  { code: "HVAC",        name: "暖通",   icon: MoveUp },
  { code: "FIRE",        name: "消防",   icon: Flame },
  { code: "ELEVATOR",    name: "电梯",   icon: MoveUp },
  { code: "CERAMIC",     name: "陶瓷",   icon: Package },
  { code: "PAINT",       name: "涂料",   icon: PaintBucket },
  { code: "WATERPROOF",  name: "防水",   icon: Umbrella },
];

// 热销商品占位:商品后台尚未接入,先静态展示骨架卡片
const HOT_PRODUCTS_PLACEHOLDER = Array.from({ length: 5 }).map((_, i) => ({
  id: `placeholder-${i}`,
  nameZh: ["3003 氟碳铝单板 2.5mm", "中空玻璃幕墙系统 LE-50", "三相异步电机 Y2-180M-4 18.5kW", "热轧 H 型钢 HW200×200×8×12", "PPR 给水管 De32×4.4mm"][i],
  priceHint: ["¥260/㎡", "¥980/㎡", "¥3,200/台", "¥4,850/吨", "¥18/m"][i],
  tier: i === 0 ? "T1" : i === 2 ? "T1" : null,
  category: ["铝单板", "幕墙", "机电", "钢结构", "给排水"][i],
}));

const FOUR_CAPABILITIES = [
  { icon: ShoppingBag, title: "严选采购商城",   desc: "覆盖铝单板、幕墙、机电等十二大品类,200+合规供应商,京东工业品模式 B2B 集采", color: "bg-[#FF6B35]" },
  { icon: Shield,      title: "供应商信用体系", desc: "9 维度 100 分评分模型,八步严审准入,T1/T2/T3 分级管理,马甲关系智能识别",       color: "bg-[#003366]" },
  { icon: Globe,       title: "国别准入合规",   desc: "8 个重点国别建材进口准入规则数据库,TBS/KEBS/SONCAP/SASO 等认证指引",            color: "bg-emerald-500" },
  { icon: Truck,       title: "履约全链追踪",   desc: "从 PO 确认到验收通过 12 节点追踪,智能预警延期风险,单据全链路数字化",            color: "bg-violet-500" },
];

const CLIENTS = ["中建集团", "中建三局", "中铁建设", "中交建设", "中国电建", "中国能建", "中冶集团", "中化集团"];

// 置灰按钮:用于跳转目标尚未实现的 CTA
function DisabledCta({ children, className = "", title = "功能开发中" }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      aria-disabled
      className={`cursor-not-allowed select-none opacity-50 ${className}`}
    >
      {children}
    </span>
  );
}

export default function HomePage() {
  return (
    <PublicLayout noContainer>
      {/* ===== HERO ===== */}
      <section className="relative min-h-[560px] flex items-center overflow-hidden">
        <div className="absolute inset-0">
          <video
            autoPlay
            muted
            loop
            playsInline
            poster="/uploads/hero-bg.jpg"
            className="w-full h-full object-cover object-center"
            style={{ filter: "brightness(0.95) saturate(1.1)" }}
          >
            <source src="/uploads/hero-video.mp4" type="video/mp4" />
          </video>
          {/* 多层渐变叠加,确保文字可读性 */}
          <div className="absolute inset-0" style={{ background: "linear-gradient(135deg, rgba(0,22,51,0.85) 0%, rgba(0,51,102,0.68) 40%, rgba(0,51,102,0.4) 70%, rgba(0,51,102,0.25) 100%)" }} />
          <div className="absolute bottom-0 left-0 right-0 h-28" style={{ background: "linear-gradient(to top, rgba(247,248,250,1) 0%, transparent 100%)" }} />
          <div className="absolute top-0 left-0 right-0 h-32" style={{ background: "linear-gradient(to bottom, rgba(0,22,51,0.3) 0%, transparent 100%)" }} />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to right, rgba(0,22,51,0.4) 0%, transparent 50%)" }} />
        </div>

        <div className="relative max-w-[1440px] mx-auto px-4 lg:px-6 py-16 w-full z-10">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* 左侧:文案 */}
            <div className="animate-fade-in">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-white/10 border border-white/20 rounded-full text-white/80 text-xs mb-5">
                <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                中央企业出海首选 B2B 工业品采购平台
              </div>
              <h1 className="text-3xl lg:text-[42px] font-black text-white leading-tight mb-4">
                海外工程材料<br />
                <span className="text-[#FF8F66]">一站式采购</span>与供应链服务
              </h1>
              <p className="text-white/60 mb-6 leading-relaxed text-sm max-w-lg">
                为央企海外工程提供建材集采、供应商信用评估、国别准入合规、履约全链追踪等一站式服务。
                覆盖钢材、幕墙、机电等十二大品类,200+合规供应商入驻,服务一带一路沿线 8 国央企项目。
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/mall"
                  className="px-7 py-3 bg-[#FF6B35] text-white font-bold rounded text-sm hover:bg-orange-600 transition shadow-lg shadow-[#FF6B35]/30"
                >
                  进入采购商城
                </Link>
                <Link
                  href="/register"
                  className="px-7 py-3 bg-white/10 border border-white/30 text-white font-semibold rounded text-sm hover:bg-white/20 transition"
                >
                  供应商入驻
                </Link>
              </div>
            </div>

            {/* 右侧:数据卡片 */}
            <div className="grid grid-cols-3 gap-3 animate-fade-in">
              {[
                { value: "200+",   label: "入驻供应商", color: "text-white" },
                { value: "500+",   label: "在售 SKU",   color: "text-white" },
                { value: "8",      label: "覆盖国家",   color: "text-white" },
                { value: "¥50亿+", label: "累计交易额", color: "text-[#FF8F66]" },
                { value: "96.8%",  label: "履约准时率", color: "text-green-400" },
                { value: "12",     label: "核心品类",   color: "text-white" },
              ].map((s) => (
                <div
                  key={s.label}
                  className="backdrop-blur-md bg-white/[0.06] border border-white/[0.12] rounded-xl p-5 text-center hover:bg-white/[0.12] hover:border-white/[0.2] transition-all duration-300 hover:-translate-y-0.5"
                >
                  <div className={`text-2xl font-black ${s.color} drop-shadow-sm`}>{s.value}</div>
                  <div className="text-[10px] text-white/50 mt-1 tracking-wide uppercase">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ===== CATEGORY GRID ===== */}
      <section className="border-b border-gray-100 bg-white">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 py-10">
          <h2 className="text-lg font-bold mb-6">品类导航</h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-12 gap-3">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              return (
                <Link
                  key={cat.code}
                  href="/mall"
                  className="flex flex-col items-center gap-2 p-4 rounded-lg border border-gray-100 hover:border-[#FF6B35] hover:shadow-md transition group cursor-pointer"
                >
                  <div className="w-10 h-10 rounded-lg bg-[#003366]/5 group-hover:bg-[#FF6B35]/10 flex items-center justify-center transition">
                    <Icon className="w-5 h-5 text-[#003366] group-hover:text-[#FF6B35] transition" />
                  </div>
                  <span className="text-xs font-medium text-gray-700 group-hover:text-[#FF6B35] transition">
                    {cat.name}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== HOT PRODUCTS(占位) ===== */}
      <section className="bg-[#f7f8fa] py-10">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold">
              热销商品
              <span className="ml-2 text-[10px] font-normal text-gray-400">(商品数据接入中,以下为示意)</span>
            </h2>
            <Link href="/mall" className="text-xs text-[#FF6B35] hover:underline flex items-center gap-1">
              查看全部 <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {HOT_PRODUCTS_PLACEHOLDER.map((p) => (
              <DisabledCta
                key={p.id}
                title="商品详情页待上线"
                className="block bg-white border border-gray-100 rounded overflow-hidden hover:border-[#FF6B35] hover:shadow-md transition group"
              >
                {/* 图片占位:渐变骨架 */}
                <div className="aspect-square bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center p-3 relative">
                  <Package className="w-12 h-12 text-slate-300" />
                  {p.tier === "T1" && (
                    <span className="absolute top-2 left-2 text-[9px] px-1.5 py-0.5 bg-[#FF6B35] text-white rounded font-bold">
                      优选
                    </span>
                  )}
                </div>
                {/* 商品信息 */}
                <div className="p-3">
                  <h3 className="text-[13px] leading-snug text-gray-800 font-medium line-clamp-2 min-h-[40px] group-hover:text-[#FF6B35] transition">
                    {p.nameZh}
                  </h3>
                  <div className="text-[#e4393c] text-lg font-bold mt-1.5">
                    {p.priceHint}
                  </div>
                  <div className="flex gap-1 mt-2">
                    {p.tier && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded border border-[#FF6B35] text-[#FF6B35] bg-[#fff7f4]">
                        {p.tier} 级
                      </span>
                    )}
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-gray-200 text-gray-500">
                      {p.category}
                    </span>
                  </div>
                  <div className="flex gap-1.5 mt-3 pt-2.5 border-t border-gray-100">
                    <span className="flex-1 py-1.5 text-center text-[11px] font-semibold bg-[#FF6B35]/70 text-white rounded">
                      询价
                    </span>
                    <span className="flex-1 py-1.5 text-center text-[11px] font-semibold border border-gray-200 text-gray-400 rounded">
                      对比
                    </span>
                  </div>
                </div>
              </DisabledCta>
            ))}
          </div>
        </div>
      </section>

      {/* ===== 平台核心能力 ===== */}
      <section className="bg-white py-14">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
          <h2 className="text-lg font-bold mb-2">平台核心能力</h2>
          <p className="text-gray-400 text-xs mb-8">为央企海外工程提供全链路数字化采购服务</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FOUR_CAPABILITIES.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.title}
                  className="bg-white border border-gray-100 rounded-xl p-6 hover:shadow-lg hover:-translate-y-0.5 transition-all group"
                >
                  <div className={`w-11 h-11 rounded-lg ${item.color} flex items-center justify-center mb-4`}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <h3 className="font-bold text-gray-900 mb-2">{item.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== AI TOOLS BANNER ===== */}
      <section className="bg-gradient-to-r from-[#001833] to-[#003366] py-12">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-6 h-6 text-[#FF6B35]" />
                <h2 className="text-lg font-bold text-white">AI 智能体工具箱</h2>
                <span className="text-[9px] px-2 py-0.5 bg-[#FF6B35]/20 text-[#FF6B35] rounded-full font-semibold">
                  Claude AI 驱动
                </span>
              </div>
              <p className="text-white/50 text-sm">
                9 大 AI Agent 覆盖证书审查、报价比价、国别准入、风险预警等全场景智能决策
              </p>
            </div>
            <Link
              href="/ai"
              className="px-6 py-2.5 bg-[#FF6B35] text-white font-semibold rounded text-sm hover:bg-orange-600 transition flex items-center gap-2 flex-shrink-0"
            >
              进入工具箱 <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ===== CLIENTS ===== */}
      <section className="bg-[#f7f8fa] py-10 border-t border-gray-100">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 text-center">
          <h2 className="text-lg font-bold mb-6">服务客户</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            {CLIENTS.map((name) => (
              <div
                key={name}
                className="bg-white rounded p-4 border border-gray-100 text-sm font-bold text-gray-400 hover:text-[#003366] hover:border-[#003366]/20 transition"
              >
                {name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="bg-gradient-to-r from-[#001833] to-[#003366] py-14">
        <div className="max-w-[1440px] mx-auto px-4 lg:px-6 text-center">
          <h2 className="text-2xl font-bold text-white mb-3">开启您的海外供应链数字化之旅</h2>
          <p className="text-white/50 text-sm mb-6">
            加入 200+ 认证供应商与数十家央企采购团队,共建可信赖的海外建材供应链生态
          </p>
          <div className="flex justify-center gap-3">
            <Link
              href="/register"
              className="px-8 py-3 bg-[#FF6B35] text-white font-bold rounded text-sm hover:bg-orange-600 transition shadow-lg shadow-[#FF6B35]/30"
            >
              立即注册
            </Link>
            <DisabledCta
              title="关于页面待上线"
              className="px-8 py-3 bg-white/10 border border-white/30 text-white font-semibold rounded text-sm"
            >
              了解更多
            </DisabledCta>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
