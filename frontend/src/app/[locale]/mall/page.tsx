"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, SlidersHorizontal, ChevronRight, X } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import type { CategoryTreeNode } from "@/lib/api/categories";

// PRD v2.0 §2.2 C5:Filter bar 国家/级别 UI 保留,纯视觉,不接后端
const countries = [
  { code: "", name: "全部国家" },
  { code: "TZ", name: "坦桑尼亚" },
  { code: "KE", name: "肯尼亚" },
  { code: "DZ", name: "阿尔及利亚" },
  { code: "SA", name: "沙特阿拉伯" },
  { code: "AE", name: "阿联酋" },
  { code: "NG", name: "尼日利亚" },
  { code: "EG", name: "埃及" },
  { code: "ZA", name: "南非" },
];

const tiers = [
  { code: "", name: "全部级别" },
  { code: "T1", name: "T1 头部" },
  { code: "T2", name: "T2 优质" },
  { code: "T3", name: "T3 认证" },
];

function findCategoryNode(
  categories: CategoryTreeNode[],
  code: string
): CategoryTreeNode | null {
  for (const c of categories) {
    if (c.code === code) return c;
    const matched = findCategoryNode(c.children || [], code);
    if (matched) return matched;
  }
  return null;
}

function categoryContainsCode(category: CategoryTreeNode, code: string): boolean {
  if (category.code === code) return true;
  return (category.children || []).some((child) => categoryContainsCode(child, code));
}

function MallContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlCat = searchParams.get("cat") || "";

  const { tree: categoryTree, isLoading: loadingCategories } = useCategoryTree();

  const [selectedCategory, setSelectedCategory] = useState(urlCat);
  const [hoveredLevel1, setHoveredLevel1] = useState("");
  const [expandedLevel1, setExpandedLevel1] = useState("");
  const [selectedCountry, setSelectedCountry] = useState("");
  const [selectedTier, setSelectedTier] = useState("");
  const [searchInput, setSearchInput] = useState("");

  // URL 变化(后退/前进 / 直接编辑地址栏)→ state 同步
  useEffect(() => {
    if (urlCat !== selectedCategory) {
      setSelectedCategory(urlCat);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlCat]);

  // state 变化 → URL(replace 不入栈)
  const syncCategoryToUrl = (code: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (code) params.set("cat", code);
    else params.delete("cat");
    const qs = params.toString();
    router.replace(qs ? `/mall?${qs}` : "/mall", { scroll: false });
  };

  const selectedCategoryName = useMemo(
    () => findCategoryNode(categoryTree, selectedCategory)?.name || "",
    [categoryTree, selectedCategory]
  );

  const activeLevel1Category = useMemo(
    () => categoryTree.find((c) => c.code === hoveredLevel1) || null,
    [categoryTree, hoveredLevel1]
  );

  const handleCategoryClick = (code: string, closeHover = true) => {
    const next = selectedCategory === code ? "" : code;
    setSelectedCategory(next);
    syncCategoryToUrl(next);
    if (closeHover) setHoveredLevel1("");
  };

  const handleMobileLevel1Click = (category: CategoryTreeNode) => {
    handleCategoryClick(category.code, false);
    setExpandedLevel1((prev) => (prev === category.code ? "" : category.code));
  };

  const hasActiveFilters = selectedCategory || selectedCountry || selectedTier;

  const clearAll = () => {
    setSelectedCategory("");
    syncCategoryToUrl("");
    setSelectedCountry("");
    setSelectedTier("");
    setSearchInput("");
    setHoveredLevel1("");
  };

  const categoryButtonClass = (category: CategoryTreeNode) => {
    const exactSelected = selectedCategory === category.code;
    const inSelectedPath =
      selectedCategory && categoryContainsCode(category, selectedCategory);
    if (exactSelected || inSelectedPath) {
      return "bg-blue-50 text-[#1D6FF2] font-semibold";
    }
    return "text-gray-700 hover:bg-blue-50 hover:text-[#1D6FF2]";
  };

  return (
    <PublicLayout>
      <div className="space-y-7">
        {/* Hero */}
        <section className="rounded-2xl bg-white border border-gray-100 shadow-sm px-8 py-7">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-[#003366]">
              严选商城
              <span className="block w-12 h-1 bg-[#FF6B35] rounded-full mt-2" />
            </h1>
            <p className="text-gray-500 text-sm mt-2">
              精选全球建材供应商,严格质量认证
            </p>
          </div>
          {/* 搜索 UI 保留(PRD §1.3 不做真实搜索),form 不接 onSubmit */}
          <form
            onSubmit={(e) => e.preventDefault()}
            className="flex gap-3 max-w-2xl"
          >
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="搜索产品名称、规格、品牌..."
                className="w-full h-12 pl-12 pr-4 rounded-full border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 shadow-sm focus:outline-none focus:border-[#003366] focus:ring-2 focus:ring-[#003366]/10 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled
              className="h-12 px-7 rounded-full bg-[#003366] hover:bg-[#002244] text-white font-semibold text-sm shadow-sm transition-colors shrink-0 disabled:opacity-60 disabled:cursor-not-allowed"
              title="搜索功能开发中"
            >
              搜索
            </button>
          </form>
        </section>

        <div className="flex flex-col lg:flex-row gap-7">
          {/* Sidebar */}
          <aside className="lg:w-56 shrink-0">
            <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
              <h3 className="font-semibold text-gray-800 text-sm mb-4 flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-[#003366]" />
                产品分类
              </h3>

              {/* Desktop: hover 飞出二级面板 */}
              <div
                className="relative hidden lg:block"
                onMouseLeave={() => setHoveredLevel1("")}
              >
                <ul className="space-y-1.5">
                  <li>
                    <button
                      onClick={() => handleCategoryClick("")}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold transition-all relative ${
                        selectedCategory === ""
                          ? "bg-blue-50 text-[#1D6FF2]"
                          : "text-gray-700 hover:bg-blue-50 hover:text-[#1D6FF2]"
                      }`}
                    >
                      {selectedCategory === "" && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[#1D6FF2] rounded-r-full" />
                      )}
                      全部分类
                    </button>
                  </li>
                  {loadingCategories ? (
                    <li className="px-3 py-2 text-sm text-gray-400">
                      分类加载中...
                    </li>
                  ) : (
                    categoryTree.map((cat) => (
                      <li key={cat.code}>
                        <button
                          onClick={() => handleCategoryClick(cat.code)}
                          onMouseEnter={() => setHoveredLevel1(cat.code)}
                          className={`w-full rounded-lg px-3 py-2.5 text-left transition-all relative group ${
                            hoveredLevel1 === cat.code
                              ? "bg-blue-50 text-[#1D6FF2]"
                              : categoryButtonClass(cat)
                          }`}
                        >
                          {(selectedCategory === cat.code ||
                            hoveredLevel1 === cat.code ||
                            categoryContainsCode(cat, selectedCategory)) && (
                            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-[#1D6FF2] rounded-r-full" />
                          )}
                          <span className="flex items-center justify-between gap-2">
                            <span className="truncate text-sm font-semibold">
                              {cat.name}
                            </span>
                            {(cat.children?.length || 0) > 0 && (
                              <ChevronRight className="h-4 w-4 shrink-0 text-current" />
                            )}
                          </span>
                          {(cat.children?.length || 0) > 0 && (
                            <span className="mt-1 block truncate text-xs font-normal text-gray-400 group-hover:text-[#1D6FF2]/70">
                              {cat.children
                                ?.slice(0, 2)
                                .map((child) => child.name)
                                .join(" / ")}
                            </span>
                          )}
                        </button>
                      </li>
                    ))
                  )}
                </ul>

                {activeLevel1Category &&
                  (activeLevel1Category.children?.length || 0) > 0 && (
                    <div className="absolute left-full top-0 z-30 w-[720px] max-w-[calc(100vw-22rem)] rounded-xl border border-gray-100 bg-white p-6 shadow-xl">
                      <div className="max-h-[520px] overflow-y-auto pr-2">
                        <div className="space-y-6">
                          {activeLevel1Category.children?.map((level2) => (
                            <div
                              key={level2.code}
                              className="border-b border-dashed border-gray-100 pb-5 last:border-b-0 last:pb-0"
                            >
                              <button
                                onClick={() => handleCategoryClick(level2.code)}
                                className={`mb-3 block text-left text-sm font-bold leading-6 transition-colors ${
                                  categoryContainsCode(level2, selectedCategory)
                                    ? "text-[#1D6FF2]"
                                    : "text-gray-900 hover:text-[#1D6FF2]"
                                }`}
                              >
                                {level2.name}
                              </button>
                              <div className="flex flex-wrap gap-x-5 gap-y-3">
                                {(level2.children || []).map((level3) => (
                                  <button
                                    key={level3.code}
                                    onClick={() =>
                                      handleCategoryClick(level3.code)
                                    }
                                    className={`text-left text-sm leading-6 transition-colors ${
                                      selectedCategory === level3.code
                                        ? "font-semibold text-[#1D6FF2]"
                                        : "text-gray-600 hover:text-[#1D6FF2]"
                                    }`}
                                  >
                                    {level3.name}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
              </div>

              {/* Mobile: 折叠版 */}
              <div className="lg:hidden space-y-1">
                <button
                  onClick={() => {
                    handleCategoryClick("");
                    setExpandedLevel1("");
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all relative ${
                    selectedCategory === ""
                      ? "bg-blue-50 text-[#1D6FF2] font-semibold"
                      : "text-gray-700 hover:bg-blue-50 hover:text-[#1D6FF2]"
                  }`}
                >
                  全部分类
                </button>
                {loadingCategories ? (
                  <div className="px-3 py-2 text-sm text-gray-400">
                    分类加载中...
                  </div>
                ) : (
                  categoryTree.map((cat) => (
                    <div key={cat.code}>
                      <button
                        onClick={() => handleMobileLevel1Click(cat)}
                        className={`w-full px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between gap-2 ${categoryButtonClass(
                          cat
                        )}`}
                      >
                        <span className="min-w-0 text-left">
                          <span className="block font-semibold">
                            {cat.name}
                          </span>
                          {(cat.children?.length || 0) > 0 && (
                            <span className="block truncate text-xs font-normal text-gray-400">
                              {cat.children
                                ?.slice(0, 2)
                                .map((child) => child.name)
                                .join(" / ")}
                            </span>
                          )}
                        </span>
                        {(cat.children?.length || 0) > 0 && (
                          <ChevronRight
                            className={`h-3.5 w-3.5 transition-transform ${
                              expandedLevel1 === cat.code ? "rotate-90" : ""
                            }`}
                          />
                        )}
                      </button>
                      {expandedLevel1 === cat.code && (
                        <div className="mt-2 space-y-4 border-l border-gray-100 pl-3">
                          {cat.children?.map((level2) => (
                            <div key={level2.code} className="space-y-2">
                              <button
                                onClick={() =>
                                  handleCategoryClick(level2.code, false)
                                }
                                className={`text-left text-sm font-bold transition-colors ${
                                  categoryContainsCode(level2, selectedCategory)
                                    ? "text-[#1D6FF2]"
                                    : "text-gray-900 hover:text-[#1D6FF2]"
                                }`}
                              >
                                {level2.name}
                              </button>
                              <div className="flex flex-wrap gap-x-4 gap-y-2">
                                {level2.children?.map((level3) => (
                                  <button
                                    key={level3.code}
                                    onClick={() =>
                                      handleCategoryClick(level3.code, false)
                                    }
                                    className={`text-left text-sm transition-colors ${
                                      selectedCategory === level3.code
                                        ? "font-semibold text-[#1D6FF2]"
                                        : "text-gray-600 hover:text-[#1D6FF2]"
                                    }`}
                                  >
                                    {level3.name}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </aside>

          {/* Main */}
          <div className="flex-1 min-w-0 space-y-5">
            {/* Filter bar(纯视觉,PRD §2.2 C5)*/}
            <div className="bg-white rounded-2xl px-5 py-4 shadow-sm border border-gray-100 flex flex-wrap gap-3 items-center">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wide shrink-0">
                  出口国家
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {countries.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => setSelectedCountry(c.code)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                        selectedCountry === c.code
                          ? "bg-[#003366] text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="w-px h-6 bg-gray-200 hidden lg:block" />

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wide shrink-0">
                  供应商级别
                </span>
                <div className="flex gap-1.5">
                  {tiers.map((t) => (
                    <button
                      key={t.code}
                      onClick={() => setSelectedTier(t.code)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                        selectedTier === t.code
                          ? "bg-[#FF6B35] text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>

              {hasActiveFilters && (
                <button
                  onClick={clearAll}
                  className="ml-auto flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#FF6B35] transition-colors font-medium"
                >
                  <X className="h-3.5 w-3.5" />
                  清除筛选
                </button>
              )}
            </div>

            {/* 主区占位(PRD §5.3,Q1 已确认 A)*/}
            {selectedCategory ? (
              <div className="bg-white rounded-2xl py-24 px-6 text-center border border-gray-100 shadow-sm">
                <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Search className="h-7 w-7 text-gray-300" />
                </div>
                <p className="text-base font-medium text-gray-600">
                  商品功能开发中,当前选中分类:
                  <span className="ml-2 font-bold text-[#003366]">
                    {selectedCategoryName || selectedCategory}
                  </span>
                </p>
                <p className="text-sm text-gray-400 mt-2">
                  code = <code className="font-mono text-gray-500">{selectedCategory}</code>
                </p>
                <button
                  onClick={() => handleCategoryClick("")}
                  className="mt-4 px-5 py-2 rounded-full bg-[#003366] text-white text-sm font-medium hover:bg-[#002244] transition-colors"
                >
                  返回全部分类
                </button>
              </div>
            ) : (
              <div className="bg-white rounded-2xl py-24 px-6 text-center border border-gray-100 shadow-sm">
                <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Search className="h-7 w-7 text-gray-300" />
                </div>
                <p className="text-base font-medium text-gray-600">
                  商品功能开发中
                </p>
                <p className="text-sm text-gray-400 mt-2">
                  左侧选择分类查看品类结构
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}

// useSearchParams 在 Next.js 14 严格模式下必须包 Suspense
export default function MallPage() {
  return (
    <Suspense fallback={null}>
      <MallContent />
    </Suspense>
  );
}
