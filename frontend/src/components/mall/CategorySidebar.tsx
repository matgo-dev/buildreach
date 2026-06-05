"use client";

import { Phone, MessageCircle, ShieldCheck, FileCheck } from "lucide-react";

export interface CategoryItem {
  code: string;
  name_zh: string;
  name_en: string;
  level: number;
}

/* 品类中英对照 */
const CATEGORY_LABELS: Record<string, { zh: string; en: string }> = {
  "照明电气": { zh: "照明电气", en: "Lighting" },
  "卫浴洁具": { zh: "卫浴五金", en: "Sanitary Ware" },
  "管材管件": { zh: "管材管件", en: "Pipes & Fittings" },
  "板材与吊顶": { zh: "板材", en: "Boards" },
  "涂料化工": { zh: "涂料化工", en: "Paints & Chemicals" },
  "手动工具与电动工具": { zh: "工具", en: "Tools" },
  "安全装备": { zh: "劳保用品", en: "Safety Gear" },
  "紧固件": { zh: "紧固件", en: "Fasteners" },
  "门窗": { zh: "门窗建材", en: "Doors & Windows" },
  "屋面材料": { zh: "屋面材料", en: "Roofing" },
  "防水材料": { zh: "防水材料", en: "Waterproofing" },
  "瓷砖石材": { zh: "瓷砖石材", en: "Tiles & Stone" },
  "水泥与砂浆": { zh: "水泥混凝土", en: "Cement & Concrete" },
  "劳保用品": { zh: "劳保用品", en: "Labor Protection" },
  "工业用品": { zh: "工业用品", en: "Industrial Supplies" },
  "包装与物流": { zh: "包装与物流", en: "Packaging & Logistics" },
  "电工电料": { zh: "电工电料", en: "Electrical" },
};

export function getCategoryLabel(c: CategoryItem) {
  return CATEGORY_LABELS[c.name_zh] || { zh: c.name_zh || c.name_en, en: c.name_en || "" };
}

interface CategorySidebarProps {
  categories: CategoryItem[];
  activeCode: string;
  onSelect: (code: string) => void;
}

export function CategorySidebar({ categories, activeCode, onSelect }: CategorySidebarProps) {
  return (
    <aside className="w-[200px] shrink-0 space-y-3">
      {/* 品类列表 */}
      <div className="text-[13px]">
        <button
          onClick={() => onSelect("")}
          className={`w-full py-2 px-1 text-left font-bold border-b border-slate-100 ${
            !activeCode ? "text-[#0D4D4D]" : "text-slate-800 hover:text-[#0D4D4D]"
          }`}
        >
          全部商品分类 / All Categories
        </button>
        <div className="mt-1 space-y-0">
          {categories.map((c) => {
            const label = getCategoryLabel(c);
            const isActive = activeCode === c.code;
            return (
              <button
                key={c.code}
                onClick={() => onSelect(c.code)}
                className={`flex w-full items-center gap-1.5 py-2 px-1 text-left transition-colors ${
                  isActive ? "font-medium text-[#0D4D4D]" : "text-slate-600 hover:text-[#0D4D4D]"
                }`}
              >
                <span className="text-[13px]">{label.zh}</span>
                <span className="text-[11px] text-slate-400">{label.en}</span>
              </button>
            );
          })}
          <button className="flex w-full items-center gap-1.5 py-2 px-1 text-left text-slate-500 hover:text-[#0D4D4D]">
            <span className="text-[13px]">更多品类</span>
            <span className="text-[11px] text-slate-400">More Categories</span>
          </button>
        </div>
      </div>

      {/* WhatsApp 客服 */}
      <div className="pt-4 border-t border-slate-100">
        <p className="text-[13px] font-bold text-[#0D4D4D]">WhatsApp 客服</p>
        <p className="text-[14px] font-bold text-[#0D4D4D]">+255 697 123 456</p>
        <div className="mt-2 text-[11px] text-slate-500">
          <p className="flex items-center gap-1"><ShieldCheck className="h-3 w-3 text-[#0D4D4D]" />安全交易 / Secure Payment</p>
          <p className="flex items-center gap-1"><FileCheck className="h-3 w-3 text-[#0D4D4D]" />Pay to Company Account</p>
        </div>
      </div>
    </aside>
  );
}
