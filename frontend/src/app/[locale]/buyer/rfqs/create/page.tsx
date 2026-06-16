"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
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
  expected_delivery_date: string;
  target_currency: string;
  certifications: string[];
  remark: string;
  manualItems: ManualItem[];
}

function emptyDraft(): DraftData {
  return {
    contact_name: "",
    contact_phone: "",
    contact_email: "",
    requested_delivery_place: "",
    expected_delivery_date: "",
    target_currency: "USD",
    certifications: [],
    remark: "",
    manualItems: [],
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
      <div className="mx-4 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl">
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
            <div className="space-y-1">
              {products.map((p) => {
                const isExpanded = expandedId === p.id;
                const variantData = productVariantMap[p.id];
                return (
                  <div key={p.id} className="rounded-lg border border-gray-100">
                    {/* SPU 行 */}
                    <button
                      type="button"
                      onClick={() => toggleExpand(p.id)}
                      className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50"
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 shrink-0 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0 text-gray-400" />
                      )}
                      {p.main_image && (
                        <img
                          src={p.main_image}
                          alt={p.name}
                          className="h-10 w-10 shrink-0 rounded border border-gray-100 object-cover"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-gray-800">{p.name}</div>
                        <div className="text-xs text-gray-400">
                          {p.spu_code}
                        </div>
                      </div>
                    </button>

                    {/* 变体选择器 */}
                    {isExpanded && (
                      <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3 pl-11">
                        {variantData?.loading && (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                          </div>
                        )}
                        {variantData && !variantData.loading && (
                          <>
                            {variantData.variants.length > 0 ? (
                              <div className="space-y-3">
                                {variantData.variants.map((axis) => {
                                  const selected = variantSelection[p.id]?.[axis.key];
                                  return (
                                    <div key={axis.key}>
                                      <div className="mb-1.5 text-xs font-medium text-gray-500">{axis.display}</div>
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
                                                : "border-gray-200 text-gray-600 hover:border-gray-300"
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
                            ) : null}
                            {/* 加入按钮 */}
                            <div className="mt-3">
                              {(() => {
                                const sel = variantSelection[p.id] ?? {};
                                // 构建去重 key
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
                                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                      added
                                        ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                        : "bg-[#00505a] text-white hover:bg-[#003f46]"
                                    }`}
                                  >
                                    {added ? t("alreadyAdded") : t("add")}
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

  // 解析 URL 参数
  const itemIds = useMemo(() => {
    const raw = searchParams.get("items") ?? "";
    return raw
      .split(",")
      .map((s) => parseInt(s, 10))
      .filter((n) => !isNaN(n));
  }, [searchParams]);

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
            const updated = await updateCartItem(itemId, qty);
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
    try {
      const saved = sessionStorage.getItem(draftKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        // 兼容旧版无 manualItems
        if (!parsed.manualItems) parsed.manualItems = [];
        return parsed;
      }
    } catch {}

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

  const doCreate = useCallback(async (asDraft: boolean) => {
    if (submitting || savingDraft || totalItemCount === 0) return;
    if (!idemRef.current) {
      idemRef.current = typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
    if (asDraft) setSavingDraft(true); else setSubmitting(true);
    try {
      const allItems = [
        ...cartItems.map((c) => ({
          product_id: c.product_id,
          selected_variants: c.selected_variants,
          quantity: c.quantity,
        })),
        ...manualItems.map((m) => ({
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
          expected_delivery_date: draft.expected_delivery_date
            ? `${draft.expected_delivery_date}T00:00:00Z`
            : undefined,
          target_currency: draft.target_currency || undefined,
          required_certifications:
            draft.certifications.length > 0 ? draft.certifications : undefined,
          remark: draft.remark || undefined,
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
      if (err instanceof ApiError && err.messageKey) {
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
  }, [submitting, savingDraft, totalItemCount, cartItems, manualItems, draft, draftKey, syncFromCart, triggerRefresh, toast, t, tError, router, locale]);

  const handleSubmit = useCallback(() => doCreate(false), [doCreate]);
  const handleSaveDraft = useCallback(() => doCreate(true), [doCreate]);

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
          onClick={() => router.back()}
          className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-xl font-bold text-gray-800">{t("create")}</h1>
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

      {/* 区块 1：商品清单 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
                <th className="px-5 py-2.5 font-medium">{t("skuSpec")}</th>
                <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
                <th className="w-12 px-3 py-2.5" />
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
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleRemoveCartItem(item.item_id)}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}

              {/* 手动添加的商品 */}
              {manualItems.map((item, idx) => (
                <tr key={`manual-${item.product_id}-${idx}`} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {item.variant_display}
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
              ))}

              {/* 空状态 */}
              {totalItemCount === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center">
                    <ShoppingCart className="mx-auto mb-3 h-10 w-10 text-gray-200" />
                    <p className="text-sm text-gray-400">{t("itemsAllMissing")}</p>
                    <button
                      type="button"
                      onClick={() => router.push(`/${locale}/buyer/cart`)}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[#00505a] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#003f46]"
                    >
                      {t("backToCart")}
                    </button>
                  </td>
                </tr>
              )}

              {/* 添加商品按钮 */}
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
            <input
              type="date"
              value={draft.expected_delivery_date}
              onChange={(e) => updateDraft("expected_delivery_date", e.target.value)}
              onClick={(e) => (e.target as HTMLInputElement).showPicker?.()}
              min={todayStr}
              className="h-10 w-full cursor-pointer rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
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
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("remark")}
            </label>
            <textarea
              value={draft.remark}
              onChange={(e) => updateDraft("remark", e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#00505a] focus:ring-1 focus:ring-[#00505a]/20"
            />
          </div>
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
          disabled={savingDraft || submitting || totalItemCount === 0}
          onClick={handleSaveDraft}
          className={`inline-flex items-center gap-2 rounded-lg border px-6 py-2.5 text-sm font-medium transition-colors ${
            savingDraft || submitting || totalItemCount === 0
              ? "border-gray-200 text-gray-400 cursor-not-allowed"
              : "border-[#00505a] text-[#00505a] hover:bg-[#00505a]/5"
          }`}
        >
          {savingDraft && <Loader2 className="h-4 w-4 animate-spin" />}
          {t("saveDraft")}
        </button>
        <button
          type="button"
          disabled={submitting || savingDraft || totalItemCount === 0}
          onClick={handleSubmit}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-colors ${
            submitting || savingDraft || totalItemCount === 0
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
