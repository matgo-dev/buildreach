"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Search, X, MapPin, Package, ChevronDown, Check, Plus } from "lucide-react";

import { imageUrl } from "@/lib/env";
import { listProducts, getProduct, type ProductPublic } from "@/lib/api/products";

/** 买家询价"添加商品"选中项(中性形状,各页自行适配为 EditItem/ManualItem) */
export interface PickedProduct {
  product_id: number;
  selected_variants: Array<{ attr_name: string; value: string }>;
  product_name: string;
  variant_display: string;
  unit: string;
  quantity: number;
}

/** 去重身份 = product_id + 规范化规格指纹。与后端/创建页口径一致(排序后 JSON)。 */
export function makeVariantKey(
  productId: number,
  variants: Array<{ attr_name: string; value: string }>,
): string {
  const sorted = [...variants].sort(
    (a, b) => a.attr_name.localeCompare(b.attr_name) || a.value.localeCompare(b.value),
  );
  return `${productId}::${JSON.stringify(sorted)}`;
}

/** 规格展示:只拼值、以 " / " 连接,与后端 build_variant_display 一致(不带内部 attr_name)。 */
export function buildVariantDisplay(
  variants: Array<{ attr_name: string; value: string }>,
): string {
  const parts = variants.map((v) => v.value).filter(Boolean);
  return parts.join(" / ") || "—";
}

interface VariantAxis {
  key: string;
  values: string[];
}

interface VariantData {
  axes: VariantAxis[];
  unit: string;
  loading: boolean;
}

const PAGE_SIZE = 20;

// mall 列表回 has_variants;zone 列表回 sku_count —— 两者兼容
const hasVariants = (p: ProductPublic) => p.has_variants ?? (p.sku_count ?? 0) > 1;

export default function ProductSearchModal({
  open,
  onClose,
  onAdd,
  existingKeys,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (item: PickedProduct) => void;
  existingKeys: Set<string>;
}) {
  const t = useTranslations("rfq");

  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<ProductPublic[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  // 多规格商品:展开选轴
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [variantMap, setVariantMap] = useState<Record<number, VariantData>>({});
  const [axisSel, setAxisSel] = useState<Record<number, Record<string, string>>>({});

  const resetAll = useCallback(() => {
    setKeyword("");
    setProducts([]);
    setSearched(false);
    setPage(1);
    setHasMore(false);
    setExpandedId(null);
    setVariantMap({});
    setAxisSel({});
  }, []);

  useEffect(() => {
    if (!open) resetAll();
  }, [open, resetAll]);

  const handleSearch = useCallback(async () => {
    if (!keyword.trim()) return;
    setSearching(true);
    setSearched(true);
    setPage(1);
    setExpandedId(null);
    try {
      const res = await listProducts({ keyword: keyword.trim(), size: PAGE_SIZE, page: 1 });
      setProducts(res.items);
      setHasMore(res.items.length >= PAGE_SIZE);
    } catch {
      setProducts([]);
      setHasMore(false);
    } finally {
      setSearching(false);
    }
  }, [keyword]);

  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    const nextPage = page + 1;
    setLoadingMore(true);
    try {
      const res = await listProducts({ keyword: keyword.trim(), size: PAGE_SIZE, page: nextPage });
      setProducts((prev) => [...prev, ...res.items]);
      setPage(nextPage);
      setHasMore(res.items.length >= PAGE_SIZE);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, page, keyword]);

  // 展开某个多规格商品:懒加载可选轴
  const handleExpand = useCallback(
    async (p: ProductPublic) => {
      if (expandedId === p.id) {
        setExpandedId(null);
        return;
      }
      setExpandedId(p.id);
      if (variantMap[p.id]) return;
      setVariantMap((prev) => ({ ...prev, [p.id]: { axes: [], unit: p.unit || "PCS", loading: true } }));
      try {
        const detail = await getProduct(p.id);
        const axes: VariantAxis[] = [];
        for (const group of detail.attribute_groups ?? []) {
          for (const item of group.items ?? []) {
            if (item.selectable && item.values.length > 0) {
              axes.push({ key: item.key, values: item.values.map((v) => v.value) });
            }
          }
        }
        setVariantMap((prev) => ({
          ...prev,
          [p.id]: { axes, unit: detail.unit || p.unit || "PCS", loading: false },
        }));
      } catch {
        setVariantMap((prev) => ({ ...prev, [p.id]: { axes: [], unit: p.unit || "PCS", loading: false } }));
      }
    },
    [expandedId, variantMap],
  );

  const pickAxis = useCallback((productId: number, key: string, value: string) => {
    setAxisSel((prev) => ({ ...prev, [productId]: { ...(prev[productId] ?? {}), [key]: value } }));
  }, []);

  const variantsOf = useCallback(
    (productId: number): Array<{ attr_name: string; value: string }> => {
      const sel = axisSel[productId] ?? {};
      return Object.entries(sel)
        .filter(([, v]) => v)
        .map(([attr_name, value]) => ({ attr_name, value }));
    },
    [axisSel],
  );

  // 加入(数量默认 1,加进清单后在数量列改)
  const emit = useCallback(
    (p: ProductPublic, variants: Array<{ attr_name: string; value: string }>, unit: string) => {
      onAdd({
        product_id: p.id,
        selected_variants: variants,
        product_name: p.name,
        variant_display: variants.length > 0 ? buildVariantDisplay(variants) : "—",
        unit: unit || p.unit || "PCS",
        quantity: 1,
      });
    },
    [onAdd],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl">
        {/* 标题 */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("searchProduct")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 搜索框 */}
        <div className="border-b border-gray-100 px-5 py-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleSearch();
                  }
                }}
                placeholder={t("searchPlaceholder")}
                autoFocus
                className="h-10 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
              />
            </div>
            <button
              type="button"
              onClick={handleSearch}
              disabled={searching || !keyword.trim()}
              className="rounded-lg bg-[#00505a] px-4 text-sm font-medium text-white transition-colors hover:bg-[#003f46] disabled:bg-gray-200 disabled:text-gray-400"
            >
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : t("searchProduct")}
            </button>
          </div>
        </div>

        {/* 结果列表 */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {searching && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-[#00505a]" />
            </div>
          )}

          {!searching && searched && products.length === 0 && (
            <div className="py-12 text-center text-sm text-gray-400">{t("noSearchResult")}</div>
          )}

          {!searching && products.length > 0 && (
            <div className="space-y-2">
              {products.map((p) => {
                const variant = hasVariants(p);
                const simpleAdded = !variant && existingKeys.has(makeVariantKey(p.id, []));
                const isExpanded = expandedId === p.id;
                const data = variantMap[p.id];
                const picked = variantsOf(p.id);
                const pickedExists = existingKeys.has(makeVariantKey(p.id, picked));
                const allAxesPicked = !!data && picked.length === data.axes.length;
                return (
                  <div
                    key={p.id}
                    className={`overflow-hidden rounded-lg border transition-shadow ${
                      simpleAdded
                        ? "border-gray-100 bg-gray-50 opacity-60"
                        : isExpanded
                          ? "border-[#00505a] bg-[#00505a]/5 shadow-sm"
                          : "border-gray-200 hover:shadow-sm"
                    }`}
                  >
                    <div
                      onClick={() => variant && handleExpand(p)}
                      className={`flex gap-3 p-3 ${variant ? "cursor-pointer" : ""}`}
                    >
                      {/* 商品图 */}
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-gray-100 bg-gray-50">
                        {p.main_image ? (
                          <img src={imageUrl(p.main_image)} alt={p.name} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <Package className="h-6 w-6 text-gray-300" />
                          </div>
                        )}
                      </div>
                      {/* 商品信息 */}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-gray-800">{p.name}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500">
                          <span>{p.category_name}</span>
                          {p.origin && (
                            <span className="flex items-center gap-0.5">
                              <MapPin className="h-3 w-3" />
                              {p.origin}
                            </span>
                          )}
                          {p.brand && <span>{p.brand}</span>}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-400">
                          <span>{p.spu_code}</span>
                          {p.moq != null && p.moq > 0 && (
                            <span>MOQ: {p.moq} {p.moq_unit || p.unit || "PCS"}</span>
                          )}
                          {p.unit && <span>{t("unit")}: {p.unit}</span>}
                        </div>
                      </div>
                      {/* 右侧操作 */}
                      <div className="flex shrink-0 items-center">
                        {simpleAdded ? (
                          <span className="rounded-md bg-gray-100 px-3 py-1 text-xs font-medium text-gray-400">
                            {t("alreadyAdded")}
                          </span>
                        ) : variant ? (
                          <span className="inline-flex items-center gap-1 rounded-md border border-[#00505a]/30 px-3 py-1 text-xs font-medium text-[#00505a]">
                            {t("selectSpec")}
                            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => emit(p, [], p.unit || "PCS")}
                            className="inline-flex items-center gap-1 rounded-md bg-[#00505a] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#003f46]"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            {t("addProduct")}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 展开:选规格面板 */}
                    {variant && isExpanded && (
                      <div className="border-t border-gray-100 bg-white px-4 py-3">
                        {data?.loading ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="h-5 w-5 animate-spin text-[#00505a]" />
                          </div>
                        ) : data && data.axes.length > 0 ? (
                          <div className="space-y-3">
                            {data.axes.map((axis) => (
                              <div key={axis.key} className="flex flex-wrap items-center gap-2">
                                <span className="w-16 shrink-0 text-xs font-medium text-gray-500">{axis.key}</span>
                                {axis.values.map((v) => {
                                  const active = (axisSel[p.id] ?? {})[axis.key] === v;
                                  return (
                                    <button
                                      key={v}
                                      type="button"
                                      onClick={() => pickAxis(p.id, axis.key, v)}
                                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                        active
                                          ? "border-[#00505a] bg-[#00505a]/10 font-medium text-[#00505a]"
                                          : "border-gray-200 text-gray-600 hover:border-[#00505a]/40"
                                      }`}
                                    >
                                      {active && <Check className="h-3 w-3" />}
                                      {v}
                                    </button>
                                  );
                                })}
                              </div>
                            ))}
                            <div className="flex justify-end pt-1">
                              <button
                                type="button"
                                disabled={!allAxesPicked || pickedExists}
                                onClick={() => emit(p, picked, data.unit)}
                                className={`inline-flex items-center gap-1 rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                                  !allAxesPicked || pickedExists
                                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                    : "bg-[#00505a] text-white hover:bg-[#003f46]"
                                }`}
                              >
                                {!pickedExists && <Plus className="h-3.5 w-3.5" />}
                                {pickedExists ? t("alreadyAdded") : t("addProduct")}
                              </button>
                            </div>
                          </div>
                        ) : (
                          // has_variants 但无可选轴(异常/纯展示属性):按默认规格加
                          <div className="flex items-center justify-end">
                            <button
                              type="button"
                              disabled={existingKeys.has(makeVariantKey(p.id, []))}
                              onClick={() => emit(p, [], data?.unit || p.unit || "PCS")}
                              className={`inline-flex items-center gap-1 rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                                existingKeys.has(makeVariantKey(p.id, []))
                                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                  : "bg-[#00505a] text-white hover:bg-[#003f46]"
                              }`}
                            >
                              {existingKeys.has(makeVariantKey(p.id, [])) ? t("alreadyAdded") : t("addProduct")}
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {hasMore && (
                <div className="pt-2 text-center">
                  <button
                    type="button"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50 disabled:text-gray-400"
                  >
                    {loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    {t("loadMore")}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部:完成 */}
        <div className="flex items-center justify-end border-t border-gray-200 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-[#00505a] px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-[#003f46]"
          >
            {t("doneSelection")}
          </button>
        </div>
      </div>
    </div>
  );
}
