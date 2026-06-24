"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowLeft,
  Loader2,
  Send,
  AlertTriangle,
  Trash2,
  ShoppingCart,
  Plus,
  Search,
  X,
  ChevronDown,
  ChevronRight,
  Calendar,
  MapPin,
  Package,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import AttachmentUploader from "@/components/rfq/AttachmentUploader";
import type { AttachmentPublic } from "@/lib/api/attachments";
import { getCart, removeCartItem, updateCartItem, type CartItemPublic } from "@/lib/api/cart";
import { createRfq } from "@/lib/api/rfqs";
import { listProducts, getProduct, type ProductPublic } from "@/lib/api/products";
import { useCartStore } from "@/stores/cartStore";
import { useAuthStore } from "@/stores/authStore";

const DRAFT_KEY_PREFIX = "rfq_draft_";
const CURRENCIES = ["USD", "KES", "CNY"];

/** 去重 key：按 product_id + 规范化 variants JSON */
function makeItemKey(productId: number, variants: Array<{ attr_name: string; value: string }>) {
  const sorted = [...variants].sort((a, b) =>
    a.attr_name.localeCompare(b.attr_name) || a.value.localeCompare(b.value),
  );
  return `${productId}::${JSON.stringify(sorted)}`;
}

function createClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function getOffendingProductIds(err: ApiError): number[] {
  const data = err.data as { offending_product_ids?: unknown } | undefined;
  if (!Array.isArray(data?.offending_product_ids)) return [];
  return data.offending_product_ids.filter((id): id is number => typeof id === "number");
}

interface ManualItem {
  product_id: number;
  selected_variants: Array<{ attr_name: string; value: string }>;
  product_name: string;
  variant_display: string;
  unit: string;
  quantity: number;
}

interface DraftData {
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  requested_delivery_place: string;
  destination_port: string;
  preferred_trade_term: string;
  expected_delivery_date: string;
  target_currency: string;
  certifications: string[];
  remark: string;
  manualItems: ManualItem[];
  attachment_urls: string[];
  attachments: AttachmentPublic[];
}

function emptyDraft(): DraftData {
  return {
    contact_name: "",
    contact_phone: "",
    contact_email: "",
    requested_delivery_place: "",
    destination_port: "",
    preferred_trade_term: "",
    expected_delivery_date: "",
    target_currency: "USD",
    certifications: [],
    remark: "",
    manualItems: [],
    attachment_urls: [],
    attachments: [],
  };
}

// ---------- 认证标签输入 ----------

function CertificationTagInput({
  value,
  onChange,
  label,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  label: string;
}) {
  const [inputValue, setInputValue] = useState("");

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if ((e.key === "Enter" || e.key === ",") && inputValue.trim()) {
        e.preventDefault();
        const tag = inputValue.trim().toUpperCase();
        if (!value.includes(tag)) {
          onChange([...value, tag]);
        }
        setInputValue("");
      }
    },
    [inputValue, value, onChange],
  );

  const handleRemove = useCallback(
    (tag: string) => {
      onChange(value.filter((v) => v !== tag));
    },
    [value, onChange],
  );

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">{label}</label>
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded bg-[#00505a]/10 px-2 py-0.5 text-xs font-medium text-[#00505a]"
          >
            {tag}
            <button
              type="button"
              onClick={() => handleRemove(tag)}
              className="text-[#00505a]/50 hover:text-[#00505a]"
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="SGS, ISO9001..."
          className="min-w-[120px] flex-1 border-none bg-transparent text-sm outline-none placeholder:text-gray-400"
        />
      </div>
    </div>
  );
}

// ---------- 变体轴类型 ----------

type VariantAxis = {
  key: string;           // attr_key_en
  display: string;       // attr_key 显示名
  values: Array<{ value: string; display: string }>;
};

type ProductVariantEntry = {
  variants: VariantAxis[];  // selectable=true 的属性轴
  unit: string;
  loading: boolean;
};

// ---------- 商品搜索弹窗（SPU + 变体选择器） ----------

function ProductSearchModal({
  open,
  onClose,
  onAdd,
  existingKeys,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (item: ManualItem) => void;
  existingKeys: Set<string>;
}) {
  const t = useTranslations("rfq");
  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<ProductPublic[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [productVariantMap, setProductVariantMap] = useState<Record<number, ProductVariantEntry>>({});
  // 跟踪每个商品的变体选中状态
  const [variantSelection, setVariantSelection] = useState<Record<number, Record<string, string>>>({});

  const handleSearch = useCallback(async () => {
    if (!keyword.trim()) return;
    setSearching(true);
    setSearched(true);
    setExpandedId(null);
    try {
      const res = await listProducts({ keyword: keyword.trim(), size: 20 });
      setProducts(res.items);
    } catch {
      setProducts([]);
    } finally {
      setSearching(false);
    }
  }, [keyword]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSearch();
      }
    },
    [handleSearch],
  );

  const expandedIdRef = useRef(expandedId);
  expandedIdRef.current = expandedId;
  const variantMapRef = useRef(productVariantMap);
  variantMapRef.current = productVariantMap;

  const toggleExpand = useCallback(
    async (productId: number) => {
      if (expandedIdRef.current === productId) {
        setExpandedId(null);
        return;
      }
      setExpandedId(productId);
      if (variantMapRef.current[productId]) return;

      setProductVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: true } }));
      try {
        const detail = await getProduct(productId);
        const variants: VariantAxis[] = [];
        for (const group of detail.attribute_groups ?? []) {
          for (const item of group.items ?? []) {
            if (item.selectable && item.values.length > 0) {
              variants.push({
                key: item.key,
                display: item.key,
                values: item.values.map((v) => ({ value: v.value, display: v.value })),
              });
            }
          }
        }
        setProductVariantMap((prev) => ({
          ...prev,
          [productId]: { variants, unit: detail.unit, loading: false },
        }));
      } catch {
        setProductVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: false } }));
      }
    },
    [],
  );

  const handleAddProduct = useCallback(
    (product: ProductPublic, selection: Record<string, string>, unit: string) => {
      const selected_variants = Object.entries(selection).map(([attr_name, value]) => ({
        attr_name,
        value,
      }));
      const variant_display = selected_variants
        .map((v) => `${v.attr_name}: ${v.value}`)
        .join(" / ") || "\u2014";
      onAdd({
        product_id: product.id,
        selected_variants,
        product_name: product.name,
        variant_display,
        unit: unit || product.unit || "PCS",
        quantity: 1,
      });
    },
    [onAdd],
  );

  // 重置状态
  useEffect(() => {
    if (!open) {
      setKeyword("");
      setProducts([]);
      setSearched(false);
      setExpandedId(null);
      setProductVariantMap({});
      setVariantSelection({});
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl">
        {/* 标题 */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("searchProduct")}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
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
                onKeyDown={handleKeyDown}
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
            <div className="py-12 text-center text-sm text-gray-400">
              {t("noSearchResult")}
            </div>
          )}

          {!searching && products.length > 0 && (
            <div className="space-y-2">
              {products.map((p) => {
                const isExpanded = expandedId === p.id;
                const variantData = productVariantMap[p.id];
                const hasVariants = variantData && !variantData.loading && variantData.variants.length > 0;
                // 未展开时的快速添加（无变体商品）
                const noVariantKey = makeItemKey(p.id, []);
                const noVariantAdded = existingKeys.has(noVariantKey);
                return (
                  <div key={p.id} className="overflow-hidden rounded-lg border border-gray-200 transition-shadow hover:shadow-sm">
                    {/* 商品信息行 */}
                    <div className="flex gap-3 p-3">
                      {/* 商品图 */}
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-gray-100 bg-gray-50">
                        {p.main_image ? (
                          <img
                            src={p.main_image}
                            alt={p.name}
                            className="h-full w-full object-cover"
                          />
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
                      {/* 操作区 */}
                      <div className="flex shrink-0 flex-col items-end justify-between">
                        <button
                          type="button"
                          onClick={() => toggleExpand(p.id)}
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[#00505a] hover:bg-[#00505a]/5"
                        >
                          {isExpanded ? (
                            <>
                              {t("collapse")}
                              <ChevronDown className="h-3.5 w-3.5" />
                            </>
                          ) : (
                            <>
                              {t("selectVariant")}
                              <ChevronRight className="h-3.5 w-3.5" />
                            </>
                          )}
                        </button>
                        {/* 无变体时直接添加 */}
                        {!isExpanded && (
                          <button
                            type="button"
                            disabled={noVariantAdded}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAddProduct(p, {}, p.unit || "");
                            }}
                            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                              noVariantAdded
                                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                : "bg-[#00505a] text-white hover:bg-[#003f46]"
                            }`}
                          >
                            {noVariantAdded ? t("alreadyAdded") : t("quickAdd")}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 变体选择器（展开时） */}
                    {isExpanded && (
                      <div className="border-t border-gray-100 bg-gray-50/60 px-4 py-3">
                        {variantData?.loading && (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                          </div>
                        )}
                        {variantData && !variantData.loading && (
                          <>
                            {hasVariants ? (
                              <div className="space-y-3">
                                {variantData.variants.map((axis) => {
                                  const selected = variantSelection[p.id]?.[axis.key];
                                  return (
                                    <div key={axis.key}>
                                      <div className="mb-1.5 text-xs font-medium text-gray-600">{axis.display}</div>
                                      <div className="flex flex-wrap gap-1.5">
                                        {axis.values.map((v) => (
                                          <button
                                            key={v.value}
                                            type="button"
                                            onClick={() => {
                                              setVariantSelection((prev) => ({
                                                ...prev,
                                                [p.id]: {
                                                  ...(prev[p.id] ?? {}),
                                                  [axis.key]: prev[p.id]?.[axis.key] === v.value ? "" : v.value,
                                                },
                                              }));
                                            }}
                                            className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                              selected === v.value
                                                ? "border-[#00505a] bg-[#00505a]/10 text-[#00505a] font-medium"
                                                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                            }`}
                                          >
                                            {v.display}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <p className="text-xs text-gray-400">{t("noVariants")}</p>
                            )}
                            {/* 加入按钮 */}
                            <div className="mt-3 flex items-center justify-between">
                              <span className="text-xs text-gray-400">
                                {t("unit")}: {variantData.unit || p.unit || "PCS"}
                              </span>
                              {(() => {
                                const sel = variantSelection[p.id] ?? {};
                                const selected_variants = Object.entries(sel)
                                  .filter(([, v]) => v)
                                  .map(([attr_name, value]) => ({ attr_name, value }));
                                const itemKey = makeItemKey(p.id, selected_variants);
                                const added = existingKeys.has(itemKey);
                                return (
                                  <button
                                    type="button"
                                    disabled={added}
                                    onClick={() => handleAddProduct(p, sel, variantData.unit)}
                                    className={`rounded-md px-4 py-1.5 text-xs font-medium transition-colors ${
                                      added
                                        ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                        : "bg-[#00505a] text-white hover:bg-[#003f46]"
                                    }`}
                                  >
                                    {added ? t("alreadyAdded") : t("addWithVariant")}
                                  </button>
                                );
                              })()}
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 底部操作栏 */}
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

// ---------- 主内容 ----------

function RfqCreateContent() {
  const router = useRouter();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const t = useTranslations("rfq");
  const tMall = useTranslations("mall");
  const tError = useTranslations("error");
  const toast = useToast();
  const user = useAuthStore((s) => s.user);
  const syncFromCart = useCartStore((s) => s.syncFromCart);
  const triggerRefresh = useCartStore((s) => s.triggerRefresh);
  const dateInputRef = useRef<HTMLInputElement>(null);

  // 解析 URL 参数
  const itemIds = useMemo(() => {
    const raw = searchParams.get("items") ?? "";
    return raw
      .split(",")
      .map((s) => parseInt(s, 10))
      .filter((n) => !isNaN(n));
  }, [searchParams]);

  // 从 URL product_id 参数自动添加商品
  const productIdParam = useMemo(() => {
    const raw = searchParams.get("product_id");
    if (!raw) return null;
    const n = parseInt(raw, 10);
    return isNaN(n) ? null : n;
  }, [searchParams]);
  const productIdLoadedRef = useRef(false);

  // 入口路径区分
  const isCartPath = itemIds.length > 0;
  const isDirectPath = productIdParam !== null && !isCartPath;

  // 加载询价篮数据
  const [cartItems, setCartItems] = useState<CartItemPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [itemsWarning, setItemsWarning] = useState<string | null>(null);

  useEffect(() => {
    if (itemIds.length === 0) {
      setLoading(false);
      return;
    }

    getCart()
      .then((cart) => {
        const matched = cart.items.filter(
          (i) => itemIds.includes(i.item_id) && i.is_purchasable,
        );
        setCartItems(matched);

        if (matched.length === 0) {
          setItemsWarning(t("itemsAllMissing"));
        } else if (matched.length < itemIds.length) {
          setItemsWarning(t("itemsMissing"));
        }
      })
      .catch(() => {
        setItemsWarning(t("itemsAllMissing"));
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 删除询价行（不删询价篮，只是本次提交不含该项）
  const handleRemoveCartItem = useCallback((itemId: number) => {
    setCartItems((prev) => prev.filter((i) => i.item_id !== itemId));
    idemRef.current = null;
  }, []);

  // 修改篮中商品数量（同步更新询价篮）
  const qtyDebounceRef = useMemo(() => new Map<number, NodeJS.Timeout>(), []);

  const handleCartQuantityChange = useCallback(
    (itemId: number, qty: number) => {
      if (qty <= 0) return;
      idemRef.current = null;
      setCartItems((prev) =>
        prev.map((i) => (i.item_id === itemId ? { ...i, quantity: qty } : i)),
      );
      const existing = qtyDebounceRef.get(itemId);
      if (existing) clearTimeout(existing);
      qtyDebounceRef.set(
        itemId,
        setTimeout(async () => {
          qtyDebounceRef.delete(itemId);
          try {
            const updated = await updateCartItem(itemId, { quantity: qty });
            syncFromCart(updated);
          } catch {
            // 失败不回滚
          }
        }, 500),
      );
    },
    [qtyDebounceRef, syncFromCart],
  );

  // 草稿持久化（含 manualItems）
  const draftKey = `${DRAFT_KEY_PREFIX}${user?.id ?? "anon"}`;

  const [draft, setDraft] = useState<DraftData>(() => {
    if (typeof window === "undefined") return emptyDraft();

    // 从询价篮或商品直询进入时，不恢复旧草稿，每次都是全新请求
    const params = new URLSearchParams(window.location.search);
    const hasEntryParam = params.has("product_id") || params.has("items");

    if (!hasEntryParam) {
      try {
        const saved = sessionStorage.getItem(draftKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (!parsed.manualItems) parsed.manualItems = [];
          if (!parsed.attachment_urls) parsed.attachment_urls = [];
          if (!parsed.attachments) parsed.attachments = [];
          return parsed;
        }
      } catch {}
    }

    return {
      ...emptyDraft(),
      contact_name: user?.name ?? "",
      contact_phone: user?.phone ?? "",
      contact_email: user?.email ?? "",
    };
  });

  const manualItems = draft.manualItems;

  useEffect(() => {
    try {
      sessionStorage.setItem(draftKey, JSON.stringify(draft));
    } catch {}
  }, [draft, draftKey]);

  const updateDraft = useCallback(<K extends keyof DraftData>(key: K, value: DraftData[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    idemRef.current = null;
  }, []);

  // 手动添加商品
  const handleAddManualItem = useCallback(
    (item: ManualItem) => {
      setDraft((prev) => ({
        ...prev,
        manualItems: [...prev.manualItems, item],
      }));
      idemRef.current = null;
    },
    [],
  );

  // 手动行项的变体数据缓存 + 选中状态
  const [manualVariantMap, setManualVariantMap] = useState<Record<number, ProductVariantEntry>>({});
  const [manualVariantSelection, setManualVariantSelection] = useState<Record<number, Record<string, string>>>({});
  const [manualExpandedId, setManualExpandedId] = useState<number | null>(null);

  // 加载商品的变体轴
  const loadVariantAxes = useCallback(async (productId: number) => {
    if (manualVariantMap[productId]) return;
    setManualVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: true } }));
    try {
      const detail = await getProduct(productId);
      const variants: VariantAxis[] = [];
      for (const group of detail.attribute_groups ?? []) {
        for (const item of group.items ?? []) {
          if (item.selectable && item.values.length > 0) {
            variants.push({
              key: item.key,
              display: item.key,
              values: item.values.map((v) => ({ value: v.value, display: v.value })),
            });
          }
        }
      }
      setManualVariantMap((prev) => ({
        ...prev,
        [productId]: { variants, unit: detail.unit, loading: false },
      }));
      // 有变体时自动展开
      if (variants.length > 0) {
        setManualExpandedId(productId);
      }
    } catch {
      setManualVariantMap((prev) => ({ ...prev, [productId]: { variants: [], unit: "", loading: false } }));
    }
  }, [manualVariantMap]);

  // 应用变体选择到手动行项
  const handleApplyVariant = useCallback((idx: number, productId: number) => {
    const sel = manualVariantSelection[productId] ?? {};
    const selected_variants = Object.entries(sel)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));
    const variant_display = selected_variants
      .map((v) => `${v.attr_name}: ${v.value}`)
      .join(" / ") || "\u2014";
    setDraft((prev) => ({
      ...prev,
      manualItems: prev.manualItems.map((m, i) =>
        i === idx ? { ...m, selected_variants, variant_display } : m,
      ),
    }));
    setManualExpandedId(null);
    idemRef.current = null;
  }, [manualVariantSelection]);

  // 从 URL product_id 自动添加商品到手动列表
  useEffect(() => {
    if (!productIdParam || productIdLoadedRef.current) return;
    productIdLoadedRef.current = true;

    getProduct(productIdParam)
      .then((detail) => {
        const itemKey = makeItemKey(productIdParam, []);
        const alreadyInCart = cartItems.some(
          (i) => makeItemKey(i.product_id, i.selected_variants) === itemKey,
        );
        const alreadyManual = manualItems.some(
          (i) => makeItemKey(i.product_id, i.selected_variants) === itemKey,
        );
        if (alreadyInCart || alreadyManual) return;

        handleAddManualItem({
          product_id: detail.id,
          selected_variants: [],
          product_name: detail.name,
          variant_display: "\u2014",
          unit: detail.unit || "PCS",
          quantity: 1,
        });

        // 加载变体轴数据
        const variants: VariantAxis[] = [];
        for (const group of detail.attribute_groups ?? []) {
          for (const item of group.items ?? []) {
            if (item.selectable && item.values.length > 0) {
              variants.push({
                key: item.key,
                display: item.key,
                values: item.values.map((v) => ({ value: v.value, display: v.value })),
              });
            }
          }
        }
        setManualVariantMap((prev) => ({
          ...prev,
          [detail.id]: { variants, unit: detail.unit, loading: false },
        }));
        if (variants.length > 0) {
          setManualExpandedId(detail.id);
        }
      })
      .catch(() => {
        toast.error(t("productNotFound"));
      });
  }, [productIdParam, cartItems, manualItems, handleAddManualItem, toast, t]);

  const handleRemoveManualItem = useCallback((idx: number) => {
    setDraft((prev) => ({
      ...prev,
      manualItems: prev.manualItems.filter((_, i) => i !== idx),
    }));
    idemRef.current = null;
  }, []);

  const handleManualQtyChange = useCallback((idx: number, qty: number) => {
    if (qty <= 0) return;
    setDraft((prev) => ({
      ...prev,
      manualItems: prev.manualItems.map((m, i) =>
        i === idx ? { ...m, quantity: qty } : m,
      ),
    }));
    idemRef.current = null;
  }, []);

  const existingKeys = useMemo(() => {
    const keys = new Set<string>();
    cartItems.forEach((i) => keys.add(makeItemKey(i.product_id, i.selected_variants)));
    manualItems.forEach((i) => keys.add(makeItemKey(i.product_id, i.selected_variants)));
    return keys;
  }, [cartItems, manualItems]);

  // SKU 搜索弹窗
  const [showSearch, setShowSearch] = useState(false);

  // 全部商品数（篮中 + 手动）
  const totalItemCount = cartItems.length + manualItems.length;

  // 幂等 token
  const idemRef = useRef<string | null>(null);

  // 提交 / 保存草稿
  const [submitting, setSubmitting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // 自由询价：items 和 remark 至少一个非空
  const hasRemark = !!(draft.remark && draft.remark.trim());
  const canSubmit = totalItemCount > 0 || hasRemark;

  const doCreate = useCallback(async (asDraft: boolean) => {
    if (submitting || savingDraft || !canSubmit) return;
    if (!idemRef.current) {
      idemRef.current = createClientId();
    }
    if (asDraft) setSavingDraft(true); else setSubmitting(true);
    try {
      const availableManualItems: ManualItem[] = [];
      const unavailableManualKeys = new Set<string>();

      for (const item of manualItems) {
        try {
          await getProduct(item.product_id);
          availableManualItems.push(item);
        } catch (err) {
          if (err instanceof ApiError && (err.status === 404 || err.code === 40008)) {
            unavailableManualKeys.add(makeItemKey(item.product_id, item.selected_variants));
            continue;
          }
          throw err;
        }
      }

      if (unavailableManualKeys.size > 0) {
        setDraft((prev) => ({
          ...prev,
          manualItems: prev.manualItems.filter(
            (item) => !unavailableManualKeys.has(makeItemKey(item.product_id, item.selected_variants)),
          ),
        }));
        setItemsWarning(t("itemsMissing"));
        toast.error(t("productNotFound"));
      }

      if (cartItems.length + availableManualItems.length === 0 && !hasRemark) {
        setItemsWarning(t("itemsAllMissing"));
        return;
      }

      const allItems = [
        ...cartItems.map((c) => ({
          product_id: c.product_id,
          selected_variants: c.selected_variants,
          quantity: c.quantity,
        })),
        ...availableManualItems.map((m) => ({
          product_id: m.product_id,
          selected_variants: m.selected_variants,
          quantity: m.quantity,
        })),
      ];

      await createRfq(
        {
          items: allItems,
          as_draft: asDraft || undefined,
          contact_name: draft.contact_name || undefined,
          contact_phone: draft.contact_phone || undefined,
          contact_email: draft.contact_email || undefined,
          requested_delivery_place: draft.requested_delivery_place || undefined,
          destination_port: draft.destination_port || undefined,
          preferred_trade_term: draft.preferred_trade_term || undefined,
          expected_delivery_date: draft.expected_delivery_date
            ? `${draft.expected_delivery_date}T00:00:00Z`
            : undefined,
          target_currency: draft.target_currency || undefined,
          required_certifications:
            draft.certifications.length > 0 ? draft.certifications : undefined,
          remark: draft.remark || undefined,
          attachment_urls: draft.attachment_urls.length > 0 ? draft.attachment_urls : undefined,
          attachment_ids: draft.attachments.length > 0 ? draft.attachments.map(a => a.id) : undefined,
        },
        idemRef.current,
      );

      // 提交成功后清篮（草稿不清）
      if (!asDraft && cartItems.length > 0) {
        try {
          await Promise.all(cartItems.map((c) => removeCartItem(c.item_id)));
        } catch {}
      }

      idemRef.current = null;
      try { sessionStorage.removeItem(draftKey); } catch {}
      const updatedCart = await getCart();
      syncFromCart(updatedCart);
      triggerRefresh();
      toast.success(t(asDraft ? "saveDraftSuccess" : "submitSuccess"));
      router.push(`/${locale}/buyer/rfqs`);
    } catch (err) {
      if (err instanceof ApiError && err.code === 40506) {
        const ids = new Set(getOffendingProductIds(err));
        if (ids.size > 0) {
          setCartItems((prev) => prev.filter((item) => !ids.has(item.product_id)));
          setDraft((prev) => ({
            ...prev,
            manualItems: prev.manualItems.filter((item) => !ids.has(item.product_id)),
          }));
        }
        setItemsWarning(t("itemsMissing"));
        toast.error(t("productNotFound"));
      } else if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try {
          toast.error(tError(key, (err.messageParams ?? {}) as Record<string, string>));
        } catch {
          toast.error(err.message);
        }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
      setSavingDraft(false);
    }
  }, [submitting, savingDraft, canSubmit, hasRemark, totalItemCount, cartItems, manualItems, draft, draftKey, syncFromCart, triggerRefresh, toast, t, tError, router, locale]);

  const handleSubmit = useCallback(() => doCreate(false), [doCreate]);
  const handleSaveDraft = useCallback(() => doCreate(true), [doCreate]);
  const openDatePicker = useCallback(() => {
    const input = dateInputRef.current;
    if (!input) return;
    if (typeof input.showPicker === "function") {
      try {
        input.showPicker();
        return;
      } catch {
        // Some browsers only allow showPicker on directly focusable controls.
      }
    }
    input.focus();
    input.click();
  }, []);

  // 今天日期
  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, []);

  // ---- 渲染 ----

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#00505a]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* 页标题 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => isCartPath ? router.push(`/${locale}/buyer/cart`) : router.back()}
          className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-xl font-bold text-gray-800">
          {isCartPath ? t("backToCartEdit") : t("create")}
        </h1>
      </div>

      {/* 失效提示 */}
      {itemsWarning && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{itemsWarning}</span>
          {cartItems.length === 0 && manualItems.length === 0 && (
            <button
              type="button"
              onClick={() => router.push(`/${locale}/buyer/cart`)}
              className="ml-auto text-sm font-medium text-amber-700 underline"
            >
              {t("backToCart")}
            </button>
          )}
        </div>
      )}

      {/* 区块 0：需求描述 + 附件（主要输入） */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_description")}</h2>
        <div className="space-y-4">
          <div>
            <textarea
              value={draft.remark}
              onChange={(e) => updateDraft("remark", e.target.value)}
              rows={4}
              placeholder={t("descriptionPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
          <AttachmentUploader
            attachments={draft.attachments}
            onChange={(atts) => updateDraft("attachments", atts)}
          />
        </div>
      </div>

      {/* 区块 1：商品清单（可选） */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3 flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
          <span className="text-xs text-gray-400">{t("optional")}</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
                <th className="px-5 py-2.5 font-medium">{t("skuSpec")}</th>
                <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
                {!isCartPath && <th className="w-12 px-3 py-2.5" />}
              </tr>
            </thead>
            <tbody>
              {/* 篮中商品 */}
              {cartItems.map((item) => (
                <tr key={`cart-${item.item_id}`} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {item.variant_display ?? "\u2014"}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {isCartPath ? (
                      /* 篮子路径：只读显示数量 */
                      <div className="inline-flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-gray-800">{item.quantity}</span>
                        <span className="text-xs text-gray-500">
                          {tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}
                        </span>
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-1.5">
                        <input
                          type="number"
                          value={item.quantity}
                          onChange={(e) => {
                            const v = parseFloat(e.target.value);
                            if (!isNaN(v) && v > 0) handleCartQuantityChange(item.item_id, v);
                          }}
                          min={1}
                          className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
                        />
                        <span className="text-xs text-gray-500">
                          {tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}
                        </span>
                      </div>
                    )}
                  </td>
                  {!isCartPath && (
                    <td className="px-3 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => handleRemoveCartItem(item.item_id)}
                        className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}

              {/* 手动添加的商品 */}
              {manualItems.map((item, idx) => {
                const variantData = manualVariantMap[item.product_id];
                const isExpanded = manualExpandedId === item.product_id;
                const hasVariants = variantData && !variantData.loading && variantData.variants.length > 0;
                return (
                  <React.Fragment key={`manual-${item.product_id}-${idx}`}>
                    <tr className="border-t border-gray-100 even:bg-slate-50/50">
                      <td className="px-5 py-3 font-medium text-gray-800">
                        {item.product_name}
                      </td>
                      <td className="px-5 py-3 text-gray-500">
                        <div className="flex items-center gap-2">
                          <span>{item.variant_display}</span>
                          {/* 变体编辑按钮 */}
                          <button
                            type="button"
                            onClick={() => {
                              if (isExpanded) {
                                setManualExpandedId(null);
                              } else {
                                loadVariantAxes(item.product_id);
                                setManualExpandedId(item.product_id);
                              }
                            }}
                            className="rounded px-1.5 py-0.5 text-[10px] font-medium text-[#00505a] hover:bg-[#00505a]/5 transition-colors"
                          >
                            {isExpanded ? t("collapse") : t("selectVariant")}
                          </button>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <input
                            type="number"
                            value={item.quantity}
                            onChange={(e) => {
                              const v = parseFloat(e.target.value);
                              if (!isNaN(v) && v > 0) handleManualQtyChange(idx, v);
                            }}
                            min={1}
                            className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
                          />
                          <span className="text-xs text-gray-500">
                            {tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <button
                          type="button"
                          onClick={() => handleRemoveManualItem(idx)}
                          className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                    {/* 变体选择面板（展开时） */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={4} className="bg-gray-50/60 px-5 py-3">
                          {variantData?.loading && (
                            <div className="flex items-center justify-center py-3">
                              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                            </div>
                          )}
                          {variantData && !variantData.loading && (
                            <>
                              {hasVariants ? (
                                <div className="space-y-3">
                                  {variantData.variants.map((axis) => {
                                    const selected = manualVariantSelection[item.product_id]?.[axis.key];
                                    return (
                                      <div key={axis.key}>
                                        <div className="mb-1.5 text-xs font-medium text-gray-600">{axis.display}</div>
                                        <div className="flex flex-wrap gap-1.5">
                                          {axis.values.map((v) => (
                                            <button
                                              key={v.value}
                                              type="button"
                                              onClick={() => {
                                                setManualVariantSelection((prev) => ({
                                                  ...prev,
                                                  [item.product_id]: {
                                                    ...(prev[item.product_id] ?? {}),
                                                    [axis.key]: prev[item.product_id]?.[axis.key] === v.value ? "" : v.value,
                                                  },
                                                }));
                                              }}
                                              className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                                                selected === v.value
                                                  ? "border-[#00505a] bg-[#00505a]/10 text-[#00505a] font-medium"
                                                  : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                                              }`}
                                            >
                                              {v.display}
                                            </button>
                                          ))}
                                        </div>
                                      </div>
                                    );
                                  })}
                                  <button
                                    type="button"
                                    onClick={() => handleApplyVariant(idx, item.product_id)}
                                    className="mt-1 rounded-md bg-[#00505a] px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#003f46]"
                                  >
                                    {t("confirmVariant") ?? "确认选择"}
                                  </button>
                                </div>
                              ) : (
                                <p className="text-xs text-gray-400">{t("noVariants")}</p>
                              )}
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}

              {/* 添加商品按钮 — 始终显示（篮子路径和直询路径除外） */}
              {!isCartPath && !isDirectPath && (
                <tr className="border-t border-gray-100">
                  <td colSpan={4} className="px-5 py-3">
                    <button
                      type="button"
                      onClick={() => setShowSearch(true)}
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-[#00505a] transition-colors hover:text-[#003f46]"
                    >
                      <Plus className="h-4 w-4" />
                      {t("addProduct")}
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 区块 2：交货信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_delivery")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("deliveryPlace")}
            </label>
            <input
              type="text"
              value={draft.requested_delivery_place}
              onChange={(e) => updateDraft("requested_delivery_place", e.target.value)}
              placeholder={t("deliveryPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("deliveryDate")}
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={openDatePicker}
                className="flex h-10 w-full items-center justify-between rounded-lg border border-gray-200 px-3 text-left text-sm outline-none transition-colors focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
              >
                <span className={draft.expected_delivery_date ? "text-gray-800" : "text-gray-400"}>
                  {draft.expected_delivery_date || "YYYY-MM-DD"}
                </span>
                <Calendar className="h-4 w-4 text-gray-500" />
              </button>
              <input
                ref={dateInputRef}
                type="date"
                lang="en"
                value={draft.expected_delivery_date}
                onChange={(e) => updateDraft("expected_delivery_date", e.target.value)}
                min={todayStr}
                tabIndex={-1}
                aria-label={t("deliveryDate")}
                className="sr-only"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("currency")}
            </label>
            <select
              value={draft.target_currency}
              onChange={(e) => updateDraft("target_currency", e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("destinationPort")}
            </label>
            <input
              type="text"
              list="destination-port-options"
              value={draft.destination_port}
              onChange={(e) => updateDraft("destination_port", e.target.value)}
              placeholder={t("destinationPortPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
            <datalist id="destination-port-options">
              <option value="Dar es Salaam Port" />
              <option value="Mombasa Port" />
              <option value="Zanzibar Port" />
              <option value="Tanga Port" />
            </datalist>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("preferredTradeTerm")}
            </label>
            <input
              type="text"
              list="trade-term-options"
              value={draft.preferred_trade_term}
              onChange={(e) => updateDraft("preferred_trade_term", e.target.value)}
              placeholder={t("preferredTradeTermPlaceholder")}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
            <datalist id="trade-term-options">
              <option value="FOB" />
              <option value="CFR" />
              <option value="CIF" />
              <option value="DAP" />
              <option value="DDP" />
              <option value="EXW" />
            </datalist>
          </div>
        </div>
      </div>

      {/* 区块 3：联系方式 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_contact")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("contactName")}
            </label>
            <input
              type="text"
              value={draft.contact_name}
              onChange={(e) => updateDraft("contact_name", e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("contactPhone")}
            </label>
            <input
              type="text"
              value={draft.contact_phone}
              onChange={(e) => updateDraft("contact_phone", e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("contactEmail")}
            </label>
            <input
              type="email"
              value={draft.contact_email}
              onChange={(e) => updateDraft("contact_email", e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
        </div>
      </div>

      {/* 区块 4：附加要求 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("section_extra")}</h2>
        <div className="space-y-4">
          <CertificationTagInput
            value={draft.certifications}
            onChange={(v) => updateDraft("certifications", v)}
            label={t("certifications")}
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pb-8">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg border border-gray-200 px-6 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
        >
          {t("backToCart")}
        </button>
        <button
          type="button"
          disabled={savingDraft || submitting || !canSubmit}
          onClick={handleSaveDraft}
          className={`inline-flex items-center gap-2 rounded-lg border px-6 py-2.5 text-sm font-medium transition-colors ${
            savingDraft || submitting || !canSubmit
              ? "border-gray-200 text-gray-400 cursor-not-allowed"
              : "border-[#00505a] text-[#00505a] hover:bg-[#00505a]/5"
          }`}
        >
          {savingDraft && <Loader2 className="h-4 w-4 animate-spin" />}
          {t("saveDraft")}
        </button>
        <button
          type="button"
          disabled={submitting || savingDraft || !canSubmit}
          onClick={handleSubmit}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-colors ${
            submitting || savingDraft || !canSubmit
              ? "bg-gray-200 text-gray-400 cursor-not-allowed"
              : "bg-[#00505a] text-white hover:bg-[#003f46]"
          }`}
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          {t("create")}
        </button>
      </div>

      {/* 商品搜索弹窗 */}
      <ProductSearchModal
        open={showSearch}
        onClose={() => setShowSearch(false)}
        onAdd={(item) => {
          handleAddManualItem(item);
        }}
        existingKeys={existingKeys}
      />
    </div>
  );
}

export default function RfqCreatePage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_CREATE]}>
      <RfqCreateContent />
    </RouteGuard>
  );
}
