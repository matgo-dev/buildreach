"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowLeft,
  Loader2,
  Send,
  AlertTriangle,
  Trash2,
  ShoppingCart,
} from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { getCart, updateCartItem, type CartItemPublic } from "@/lib/api/cart";
import { createRfq } from "@/lib/api/rfqs";
import { useCartStore } from "@/stores/cartStore";
import { useAuthStore } from "@/stores/authStore";

const DRAFT_KEY_PREFIX = "rfq_draft_";
const CURRENCIES = ["USD", "KES", "CNY"];

interface DraftData {
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  requested_delivery_place: string;
  expected_delivery_date: string;
  target_currency: string;
  certifications: string[];
  remark: string;
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
            className="inline-flex items-center gap-1 rounded bg-[#0D4D4D]/10 px-2 py-0.5 text-xs font-medium text-[#0D4D4D]"
          >
            {tag}
            <button
              type="button"
              onClick={() => handleRemove(tag)}
              className="text-[#0D4D4D]/50 hover:text-[#0D4D4D]"
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
  const tCart = useTranslations("cart");
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
  const handleRemoveItem = useCallback((itemId: number) => {
    setCartItems((prev) => prev.filter((i) => i.item_id !== itemId));
  }, []);

  // 修改数量（同步更新询价篮）
  const qtyDebounceRef = useMemo(() => new Map<number, NodeJS.Timeout>(), []);

  const handleQuantityChange = useCallback(
    (itemId: number, qty: number) => {
      if (qty <= 0) return;
      // 乐观更新本地
      setCartItems((prev) =>
        prev.map((i) => (i.item_id === itemId ? { ...i, quantity: qty } : i)),
      );
      // debounce PATCH 询价篮
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
            // 失败不回滚，用户可继续调整
          }
        }, 500),
      );
    },
    [qtyDebounceRef, syncFromCart],
  );

  // 草稿持久化
  const draftKey = `${DRAFT_KEY_PREFIX}${user?.id ?? "anon"}`;

  const [draft, setDraft] = useState<DraftData>(() => {
    if (typeof window === "undefined") return emptyDraft();
    try {
      const saved = sessionStorage.getItem(draftKey);
      if (saved) return JSON.parse(saved);
    } catch {}

    // 预填用户信息
    return {
      ...emptyDraft(),
      contact_name: user?.name ?? "",
      contact_phone: user?.phone ?? "",
      contact_email: user?.email ?? "",
    };
  });

  // 保存草稿
  useEffect(() => {
    try {
      sessionStorage.setItem(draftKey, JSON.stringify(draft));
    } catch {}
  }, [draft, draftKey]);

  const updateDraft = useCallback(<K extends keyof DraftData>(key: K, value: DraftData[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }, []);

  // 提交
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (cartItems.length === 0) return;
    setSubmitting(true);
    try {
      await createRfq({
        source_type: "CART",
        cart_item_ids: cartItems.map((i) => i.item_id),
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
      });

      // 成功：清草稿 + 刷新询价篮 + 跳转
      try { sessionStorage.removeItem(draftKey); } catch {}
      const updatedCart = await getCart();
      syncFromCart(updatedCart);
      triggerRefresh();
      toast.success(t("submitSuccess"));
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
    }
  }, [cartItems, draft, draftKey, syncFromCart, triggerRefresh, toast, t, tError, router, locale]);

  // 今天日期（限制 date picker 不能选过去）
  const todayStr = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, []);

  // ---- 渲染 ----

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#0D4D4D]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
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
          {cartItems.length === 0 && (
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
              {cartItems.map((item) => (
                <tr key={item.item_id} className="border-t border-gray-100 even:bg-slate-50/50">
                  <td className="px-5 py-3 font-medium text-gray-800">
                    {item.product_name ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {item.sku_name
                      ? [item.sku_name, item.sku_code].filter(Boolean).join(" · ")
                      : [item.sku_code, item.color, item.material].filter(Boolean).join(" · ")}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <input
                        type="number"
                        value={item.quantity}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v > 0) handleQuantityChange(item.item_id, v);
                        }}
                        min={1}
                        className="h-8 w-20 rounded border border-gray-200 text-right text-sm font-semibold text-gray-800 outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
                      />
                      <span className="text-xs text-gray-500">
                        {tMall(`unit_${item.unit ?? "PCS"}` as Parameters<typeof tMall>[0])}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(item.item_id)}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                      title={cartItems.length <= 1 ? undefined : "移除"}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {cartItems.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center">
                    <ShoppingCart className="mx-auto mb-3 h-10 w-10 text-gray-200" />
                    <p className="text-sm text-gray-400">{t("itemsAllMissing")}</p>
                    <button
                      type="button"
                      onClick={() => router.push(`/${locale}/buyer/cart`)}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[#0D4D4D] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0a3d3d]"
                    >
                      {t("backToCart")}
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
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
              min={todayStr}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("currency")}
            </label>
            <select
              value={draft.target_currency}
              onChange={(e) => updateDraft("target_currency", e.target.value)}
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
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
              className="h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
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
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#0D4D4D] focus:ring-1 focus:ring-[#0D4D4D]/20"
            />
          </div>
        </div>
      </div>

      {/* 提交按钮 */}
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
          disabled={submitting || cartItems.length === 0}
          onClick={handleSubmit}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-colors ${
            submitting || cartItems.length === 0
              ? "bg-gray-200 text-gray-400 cursor-not-allowed"
              : "bg-[#0D4D4D] text-white hover:bg-[#0a3d3d]"
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
