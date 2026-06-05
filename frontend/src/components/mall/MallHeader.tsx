"use client";

import { Search, MapPin, ShoppingCart, User } from "lucide-react";
import Link from "next/link";

interface MallHeaderProps {
  keyword?: string;
  onKeywordChange?: (v: string) => void;
}

const NAV_ITEMS = [
  { zh: "首页", en: "Home", href: "/" },
  { zh: "商品分类", en: "Categories", href: "/products" },
  { zh: "报价比价", en: "Compare Quotes", href: "#" },
  { zh: "拼箱集运", en: "Shared Container", href: "#" },
  { zh: "订单追踪", en: "Order Tracking", href: "#" },
  { zh: "供应商", en: "Suppliers", href: "#" },
  { zh: "帮助", en: "Help", href: "#" },
];

export function MallHeader({ keyword, onKeywordChange }: MallHeaderProps) {
  return (
    <>
      {/* 顶部条 */}
      <div className="bg-[#0D4D4D] text-[11px] text-white/70 py-1">
        <div className="mx-auto flex h-5 max-w-[1280px] items-center justify-between px-4">
          <span>您值得信赖的中国建材采购伙伴 / Your trusted sourcing partner from China</span>
          <div className="flex items-center gap-4">
            <span>PVoC / CoC Certified</span>
            <span>帮助中心 / Help Center</span>
            <span>EN / 中文</span>
          </div>
        </div>
      </div>

      {/* 主导航 */}
      <header className="bg-[#0D4D4D] border-b border-white/10">
        <div className="mx-auto flex h-[52px] max-w-[1280px] items-center gap-4 px-4">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <div className="flex h-9 w-9 items-center justify-center rounded bg-white/10 text-base font-bold text-white">EA</div>
            <div className="hidden sm:block leading-tight">
              <p className="text-[13px] font-bold text-white">East Africa</p>
              <p className="text-[10px] text-white/60">Building Materials Hub</p>
            </div>
          </Link>

          {/* 搜索栏 */}
          <div className="flex flex-1 max-w-[520px]">
            <input
              type="text"
              placeholder="搜索产品、品牌、类目 / Search products, brands, categories..."
              className="h-[36px] flex-1 rounded-l-md bg-white pl-3 pr-3 text-[13px] text-slate-900 placeholder:text-slate-400 focus:outline-none"
              value={keyword ?? ""}
              onChange={(e) => onKeywordChange?.(e.target.value)}
            />
            <select className="h-[36px] border-l border-slate-200 bg-[#F0F0F0] px-2 text-[12px] text-slate-600">
              <option>全品类 / All Categories</option>
            </select>
            <button className="flex h-[36px] w-[42px] items-center justify-center rounded-r-md bg-[#1A6B6B] hover:bg-[#15595A]">
              <Search className="h-4 w-4 text-white" />
            </button>
          </div>

          {/* 右侧 */}
          <div className="ml-auto flex items-center gap-5 text-[12px]">
            <div className="flex items-center gap-1 text-white/80">
              <MapPin className="h-3.5 w-3.5" />
              <div className="leading-tight">
                <span className="block text-[10px] text-white/50">Dar es Salaam, TZ</span>
                <span className="block text-[10px] text-white/50">达累斯萨拉姆</span>
              </div>
            </div>
            <div className="flex items-center gap-1 text-white/80">
              <ShoppingCart className="h-4 w-4" />
              <span>TZS 1,248,500</span>
            </div>
            <div className="flex items-center gap-1 text-white/80">
              <User className="h-4 w-4" />
              <span>My Account</span>
            </div>
          </div>
        </div>

        {/* 二级导航 */}
        <nav className="mx-auto flex max-w-[1280px] items-center px-4 text-[12px] text-white/70">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.en}
              href={item.href}
              className="border-b-2 border-transparent px-3 py-2.5 whitespace-nowrap hover:border-white/40 hover:text-white transition-colors"
            >
              {item.zh} / {item.en}
            </Link>
          ))}
        </nav>
      </header>
    </>
  );
}
