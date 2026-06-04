"use client";

import Link from "next/link";
import { Cylinder, ArrowRight, Zap, Cable, Landmark, HardHat } from "lucide-react";

const categories = [
  {
    name: "铝卷",
    subtitle: "HS 7606",
    description: "覆盖 7 国准入政策、13 家核心供应商、47 个海外工程商机，支持供需全景深钻与 AI 智能匹配",
    href: "/buyer/category-analysis/aluminum",
    available: true,
    icon: Cylinder,
    stats: { suppliers: 13, projects: 47, countries: 7 },
  },
  {
    name: "光伏设备",
    subtitle: "光伏组件 / 逆变器 / 支架",
    description: "光伏组件、逆变器、支架系统全球供应链分析与产能匹配",
    href: "",
    available: false,
    icon: Zap,
  },
  {
    name: "电线电缆",
    subtitle: "电力电缆 / 通信电缆",
    description: "电力电缆、通信电缆跨国准入与供应商评估",
    href: "",
    available: false,
    icon: Cable,
  },
  {
    name: "钢材",
    subtitle: "型钢 / 板材 / 管材",
    description: "结构钢、板材、管材全球贸易壁垒与供方分析",
    href: "",
    available: false,
    icon: Landmark,
  },
  {
    name: "水泥建材",
    subtitle: "水泥 / 混凝土 / 砂石",
    description: "水泥、混凝土及骨料的区域化供应链布局分析",
    href: "",
    available: false,
    icon: HardHat,
  },
];

export default function CategoryAnalysisPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">品类分析</h1>
        <p className="mt-1 text-sm text-gray-500">
          选择品类，查看供应链全景图与商机分析
        </p>
      </div>

      <div className="space-y-3">
        {categories.map((cat) => {
          const Icon = cat.icon;

          if (cat.available) {
            return (
              <Link
                key={cat.name}
                href={cat.href}
                className="group flex items-center gap-5 rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-blue-400 hover:shadow-md"
              >
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#003366] to-[#0F4C81] text-white shadow-sm">
                  <Icon className="h-7 w-7" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-gray-900">{cat.name}</h2>
                    <span className="text-xs text-gray-400">{cat.subtitle}</span>
                    <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-200">
                      可用
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-500 line-clamp-1">{cat.description}</p>
                  {cat.stats && (
                    <div className="mt-2 flex gap-4 text-xs text-gray-400">
                      <span><b className="text-[#003366]">{cat.stats.countries}</b> 国准入</span>
                      <span><b className="text-[#003366]">{cat.stats.suppliers}</b> 家供应商</span>
                      <span><b className="text-[#003366]">{cat.stats.projects}</b> 个商机</span>
                    </div>
                  )}
                </div>
                <ArrowRight className="h-5 w-5 shrink-0 text-gray-500 transition group-hover:text-blue-500 group-hover:translate-x-1" />
              </Link>
            );
          }

          return (
            <div
              key={cat.name}
              className="flex items-center gap-5 rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-5 cursor-not-allowed"
            >
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-500">
                <Icon className="h-7 w-7" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold text-gray-500">{cat.name}</h2>
                  <span className="text-xs text-gray-500">{cat.subtitle}</span>
                  <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-400">
                    Coming Soon
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-500 line-clamp-1">{cat.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
