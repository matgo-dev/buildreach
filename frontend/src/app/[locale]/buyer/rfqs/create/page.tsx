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
  Calendar,
  MapPin,
  Package,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import AttachmentUploader from "@/components/rfq/AttachmentUploader";
import ProductSearchModal, { makeVariantKey as makeItemKey } from "@/components/rfq/ProductSearchModal";
import type { AttachmentPublic } from "@/lib/api/attachments";
import { imageUrl } from "@/lib/env";
import { getCart, removeCartItem, updateCartItem, type CartItemPublic } from "@/lib/api/cart";
import { createRfq } from "@/lib/api/rfqs";
import { listProducts, getProduct, type ProductPublic } from "@/lib/api/products";
import { zonesApi } from "@/lib/api/zones";
import { useCartStore } from "@/stores/cartStore";
import { useAuthStore } from "@/stores/authStore";

// v2: 作废旧草稿 key —— 历史上入口路径(直询)曾把商品写进共享草稿,老 sessionStorage 里
// 可能残留跨入口的 manualItem;换 key 让所有旧草稿一次性失效,不用手动清。
const DRAFT_KEY_PREFIX = "rfq_draft_v2_";
const CURRENCIES = ["USD", "KES", "CNY"];

// 去重 key(product_id + 规格指纹)统一用 ProductSearchModal 导出的 makeVariantKey,避免两处漂移。

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

/** 是否有真实规格：排除空、null 及占位符 em-dash */
function hasSpec(display: string | null | undefined): boolean {
  return !!display && display !== "—";
}

function inferZoneCodeFromReferrer(): string | null {
  if (typeof document === "undefined" || !document.referrer) return null;
  try {
    const referrer = new URL(document.referrer);
    const match = referrer.pathname.match(/(?:^|\/)zone\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

interface ManualItem {
  product_id: number;
  selected_variants: Array<{ attr_name: string; value: string }>;
  sku_id?: number | null;
  product_name: string;
  variant_display: string;
  unit: string;
  quantity: number;
  source_zone_code?: string;
}

// 篮子路径没有「手动加商品」入口,任何 manualItem 都是跨入口残留(旧草稿),稳定空引用兜底。
const EMPTY_MANUAL_ITEMS: ManualItem[] = [];

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
            className="inline-flex items-center gap-1 rounded bg-[#0c9468]/10 px-2 py-0.5 text-xs font-medium text-[#0c9468]"
          >
            {tag}
            <button
              type="button"
              onClick={() => handleRemove(tag)}
              className="text-[#0c9468]/50 hover:text-[#0c9468]"
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

  const loadPurchasableProduct = useCallback(
    async (productId: number, preferredZoneCode?: string | null) => {
      const triedZoneCodes = new Set<string>();
      const isSkippableZoneError = (err: unknown) =>
        err instanceof ApiError &&
        (err.status === 404 || err.status === 403 || err.code === 40008 || err.code === 40300);

      if (preferredZoneCode) {
        triedZoneCodes.add(preferredZoneCode);
        try {
          return await zonesApi.product(preferredZoneCode, productId);
        } catch (err) {
          if (!isSkippableZoneError(err)) {
            throw err;
          }
        }
      }

      try {
        return await getProduct(productId);
      } catch (err) {
        if (!(err instanceof ApiError) || (err.status !== 404 && err.code !== 40008)) {
          throw err;
        }
      }

      for (const z of user?.zones ?? []) {
        if (triedZoneCodes.has(z.code)) continue;
        try {
          return await zonesApi.product(z.code, productId);
        } catch (err) {
          if (isSkippableZoneError(err)) {
            continue;
          }
          throw err;
        }
      }
      throw new ApiError({ code: 40008, message: "Product not found", status: 404 });
    },
    [user?.zones],
  );

  // 解析 URL 参数
  const itemIds = useMemo(() => {
    const raw = searchParams.get("items") ?? "";
    return raw
      .split(",")
      .map((s) => parseInt(s, 10))
      .filter((n) => !isNaN(n));
  }, [searchParams]);
  const itemIdsKey = useMemo(() => itemIds.join(","), [itemIds]);

  // 从 URL product_id 参数自动添加商品
  const productIdParam = useMemo(() => {
    const raw = searchParams.get("product_id");
    if (!raw) return null;
    const n = parseInt(raw, 10);
    return isNaN(n) ? null : n;
  }, [searchParams]);
  const zoneCodeParam = useMemo(
    () => searchParams.get("zone_code") || inferZoneCodeFromReferrer(),
    [searchParams],
  );
  const productIdLoadedRef = useRef(false);

  // 入口路径区分
  const isCartPath = itemIds.length > 0;
  const isDirectPath = productIdParam !== null && !isCartPath;
  const entryKey = isCartPath
    ? `cart:${itemIdsKey}`
    : isDirectPath
      ? `product:${zoneCodeParam ?? ""}:${productIdParam}`
      : "free";

  // 加载询价篮数据
  const [cartItems, setCartItems] = useState<CartItemPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [itemsWarning, setItemsWarning] = useState<string | null>(null);

  useEffect(() => {
    if (itemIds.length === 0) {
      setCartItems([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setItemsWarning(null);
    getCart()
      .then((cart) => {
        if (cancelled) return;
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
        if (cancelled) return;
        setItemsWarning(t("itemsAllMissing"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [itemIdsKey, t]); // eslint-disable-line react-hooks/exhaustive-deps

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
  const createFreshDraft = useCallback(
    (): DraftData => ({
      ...emptyDraft(),
      contact_name: user?.name ?? "",
      contact_phone: user?.phone ?? "",
      contact_email: user?.email ?? "",
    }),
    [user?.email, user?.name, user?.phone],
  );

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
          if (!parsed.attachments) parsed.attachments = [];
          return parsed;
        }
      } catch {}
    }

    return createFreshDraft();
  });

  // 篮子路径只认篮中商品:忽略任何 manualItem(旧草稿跨入口残留),既不渲染也不提交。
  // 从设计上篮子路径本就没有手动加商品入口,这是语义正确的过滤而非补丁。
  const manualItems = isCartPath ? EMPTY_MANUAL_ITEMS : draft.manualItems;
  const entryKeyRef = useRef(entryKey);

  useEffect(() => {
    if (entryKeyRef.current === entryKey) return;
    entryKeyRef.current = entryKey;
    idemRef.current = null;
    setItemsWarning(null);

    if (isDirectPath) {
      productIdLoadedRef.current = false;
      setCartItems([]);
      setDraft(createFreshDraft());
      return;
    }

    if (isCartPath) {
      productIdLoadedRef.current = false;
      setDraft(createFreshDraft());
    }
  }, [createFreshDraft, entryKey, isCartPath, isDirectPath]);

  // 只有自由路径(无入口参数)才写共享草稿。入口路径(篮子/直询)每次从 URL/篮子重建、
  // 本就不恢复旧草稿(见 useState 初始化注释),若也写进去会把直询商品污染进自由路径的恢复 → 跨入口残留。
  const isFreePath = !isCartPath && !isDirectPath;
  useEffect(() => {
    if (!isFreePath) return;
    try {
      sessionStorage.setItem(draftKey, JSON.stringify(draft));
    } catch {}
  }, [draft, draftKey, isFreePath]);

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

  // 从 URL product_id 自动添加商品到手动列表
  useEffect(() => {
    if (!productIdParam) return;
    if (!user) return;
    const itemKey = makeItemKey(productIdParam, []);
    const hasOnlyDirectItem =
      cartItems.length === 0 &&
      manualItems.length === 1 &&
      makeItemKey(manualItems[0].product_id, manualItems[0].selected_variants) === itemKey &&
      (manualItems[0].source_zone_code ?? null) === zoneCodeParam;
    if (productIdLoadedRef.current && hasOnlyDirectItem) return;
    productIdLoadedRef.current = true;

    // \u7ade\u6001\u9632\u62a4\uff1a\u82e5\u5728 fetch \u672a\u8fd4\u56de\u524d\u5207\u6362\u4e86\u5165\u53e3(\u5982\u76f4\u8be2\u2192\u8be2\u4ef7\u7bee),cleanup \u7f6e cancelled\uff0c
    // \u8fdf\u5230\u7684 resolve \u4e0d\u5f97\u518d\u5199\u5165\u8349\u7a3f\u2014\u2014\u5426\u5219\u4f1a\u628a\u4e0a\u4e00\u4e2a\u76f4\u8be2\u5546\u54c1\u6cc4\u6f0f\u8fdb\u5f53\u524d\u7bee\u5b50\u8def\u5f84\u3002
    let cancelled = false;
    loadPurchasableProduct(productIdParam, zoneCodeParam)
      .then((detail) => {
        if (cancelled) return;
        setCartItems([]);
        setDraft((prev) => ({
          ...prev,
          manualItems: [{
            product_id: detail.id,
            selected_variants: [],
            product_name: detail.name,
            // \u672a\u9009\u89c4\u683c \u2192 \u63d0\u4ea4\u65f6\u540e\u7aef\u89e3\u6790\u5230 is_default SKU;\u8fd9\u91cc\u7528\u540e\u7aef\u9884\u7b97\u597d\u7684\u9ed8\u8ba4\u89c4\u683c\u4e32\u5c55\u793a\uff0c
            // \u4e0e\u300c\u52a0\u8d2d\u7269\u7bee\u300d\u843d\u5230\u540c\u4e00\u9ed8\u8ba4 SKU \u7684\u663e\u793a\u4e00\u81f4\uff08\u7b80\u5355\u5546\u54c1\u4e3a null \u2192 \u663e\u793a\u65e0\u5177\u4f53\u89c4\u683c\uff09\u3002
            variant_display: detail.default_variant_display || "\u2014",
            unit: detail.unit || "PCS",
            quantity: 1,
            source_zone_code: zoneCodeParam ?? undefined,
          }],
        }));
        idemRef.current = null;
      })
      .catch(() => {
        if (cancelled) return;
        productIdLoadedRef.current = false;
        toast.error(t("productNotFound"));
      });
    return () => {
      cancelled = true;
    };
  }, [productIdParam, zoneCodeParam, user, cartItems, manualItems, loadPurchasableProduct, toast, t]);

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
          await loadPurchasableProduct(item.product_id, item.source_zone_code);
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
          sku_id: m.sku_id,
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
  }, [submitting, savingDraft, canSubmit, hasRemark, totalItemCount, cartItems, manualItems, draft, draftKey, loadPurchasableProduct, syncFromCart, triggerRefresh, toast, t, tError, router, locale]);

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
        <Loader2 className="h-8 w-8 animate-spin text-[#0c9468]" />
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
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
                  <td className={`px-5 py-3 align-top text-xs ${hasSpec(item.variant_display) ? "text-gray-600" : "text-gray-400"}`}>
                    {hasSpec(item.variant_display) ? item.variant_display : t("noSpec")}
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
                          className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              {manualItems.map((item, idx) => (
                <tr key={`manual-${item.product_id}-${idx}`} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name}
                  </td>
                  <td className={`px-5 py-3 align-top text-xs ${hasSpec(item.variant_display) ? "text-gray-600" : "text-gray-400"}`}>
                    {hasSpec(item.variant_display) ? item.variant_display : t("noSpec")}
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
                        className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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

              {/* 添加商品按钮 — 始终显示（篮子路径和直询路径除外） */}
              {!isCartPath && !isDirectPath && (
                <tr className="border-t border-gray-100">
                  <td colSpan={4} className="px-5 py-3">
                    <button
                      type="button"
                      onClick={() => setShowSearch(true)}
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0c9468] transition-colors hover:text-[#0a7a56]"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
                className="flex h-10 w-full items-center justify-between rounded-lg border border-gray-200 px-3 text-left text-sm outline-none transition-colors focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0c9468] focus:ring-1 focus:ring-[#0c9468]/20"
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
              : "border-[#0c9468] text-[#0c9468] hover:bg-[#0c9468]/5"
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
              : "bg-[#0c9468] text-white hover:bg-[#0a7a56]"
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
