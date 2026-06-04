"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function AluminumSupplyChainPage() {
  return (
    <div
      className="fixed top-16 left-60 right-0 bottom-0 flex flex-col bg-white"
      style={{ zIndex: 10 }}
    >
      {/* 顶部导航栏 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200 bg-white shrink-0">
        <Link
          href="/buyer/category-analysis"
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 transition"
        >
          <ArrowLeft className="h-4 w-4" />
          返回品类列表
        </Link>
        <span className="text-gray-300">|</span>
        <h1 className="text-sm font-semibold text-gray-900">
          铝卷海外供应链全景图
        </h1>
        <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
          Demo
        </span>
      </div>

      {/* iframe 撑满剩余空间 */}
      <iframe
        src="/demos/aluminum-supply-chain.html"
        className="flex-1 w-full border-0"
        title="铝卷海外供应链全景图"
      />
    </div>
  );
}
