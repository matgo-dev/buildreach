"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, Loader2, Plus, X, Search } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/lib/permissions";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { createRfq } from "@/lib/api/rfqs";
import { operatorProductsApi, type ProductOperatorItem } from "@/lib/api/operatorProducts";
import { getProduct, type AttrItem } from "@/lib/api/products";
import { searchBuyerOrgs, type BuyerOrgBrief } from "@/lib/api/operatorBuyers";

// ---------- 本地行项类型 ----------

interface LocalItem {
  /** 用于去重的 key: product_id + 排序后 variants */
  dedupeKey: string;
  product_id: number;
  product_name: string;
  selected_variants: Array<{ attr_name: string; value: string }>;
  variant_display: string;
  quantity: number;
  remark: string;
}

function buildDedupeKey(
  productId: number,
  variants: Array<{ attr_name: string; value: string }>,
): string {
  const sorted = [...variants]
    .sort((a, b) => a.attr_name.localeCompare(b.attr_name))
    .map((v) => `${v.attr_name}=${v.value}`)
    .join("|");
  return `${productId}::${sorted}`;
}

function buildVariantDisplay(
  variants: Array<{ attr_name: string; value: string }>,
): string {
  if (variants.length === 0) return "";
  return variants.map((v) => `${v.attr_name}: ${v.value}`).join(", ");
}

// ---------- 变体选择器 ----------

interface VariantSelectorProps {
  selectableAttrs: AttrItem[];
  selected: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

function VariantSelector({ selectableAttrs, selected, onChange }: VariantSelectorProps) {
  if (selectableAttrs.length === 0) return null;
  return (
    <div className="space-y-3">
      {selectableAttrs.map((attr) => (
        <div key={attr.key}>
          <p className="mb-1.5 text-xs font-medium text-gray-500">{attr.key}</p>
          <div className="flex flex-wrap gap-1.5">
            {attr.values.map((v) => {
              const active = selected[attr.key] === v.value;
              return (
                <button
                  key={v.value}
                  type="button"
                  onClick={() => onChange(attr.key, active ? "" : v.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "border-blue-500 bg-blue-50 text-blue-700"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {v.value}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- 添加商品弹窗 ----------

interface AddItemModalProps {
  existingKeys: Set<string>;
  onClose: () => void;
  onAdd: (item: LocalItem) => void;
}

function AddItemModal({ existingKeys, onClose, onAdd }: AddItemModalProps) {
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<ProductOperatorItem[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const [selectedProduct, setSelectedProduct] = useState<ProductOperatorItem | null>(null);
  const [selectableAttrs, setSelectableAttrs] = useState<AttrItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedVariants, setSelectedVariants] = useState<Record<string, string>>({});
  const [quantity, setQuantity] = useState("1");
  const [remark, setRemark] = useState("");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 防抖搜索商品
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await operatorProductsApi.list({ keyword: query.trim(), status: "ACTIVE", size: 10 });
        setResults(res.items);
        setShowDropdown(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [query]);

  // 选中商品 → 拉详情获取 selectable 属性
  const handleSelectProduct = useCallback(async (product: ProductOperatorItem) => {
    setSelectedProduct(product);
    setShowDropdown(false);
    setQuery(product.name);
    setSelectedVariants({});
    setSelectableAttrs([]);
    setLoadingDetail(true);
    try {
      const detail = await getProduct(product.id);
      const selectable: AttrItem[] = [];
      for (const group of detail.attribute_groups) {
        for (const item of group.items) {
          if (item.selectable) selectable.push(item);
        }
      }
      setSelectableAttrs(selectable);
    } catch {
      // 无属性或接口异常，静默处理
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const handleVariantChange = useCallback((key: string, value: string) => {
    setSelectedVariants((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  const handleAdd = useCallback(() => {
    if (!selectedProduct) return;
    const qty = Number(quantity);
    if (!qty || qty <= 0) {
      toast.error(t("quantity") + " > 0");
      return;
    }

    const variants = Object.entries(selectedVariants)
      .filter(([, v]) => v)
      .map(([attr_name, value]) => ({ attr_name, value }));

    const key = buildDedupeKey(selectedProduct.id, variants);
    if (existingKeys.has(key)) {
      toast.error(t("alreadyAdded"));
      return;
    }

    onAdd({
      dedupeKey: key,
      product_id: selectedProduct.id,
      product_name: selectedProduct.name,
      selected_variants: variants,
      variant_display: buildVariantDisplay(variants),
      quantity: qty,
      remark: remark.trim(),
    });
    onClose();
  }, [selectedProduct, selectedVariants, quantity, remark, existingKeys, onAdd, onClose, toast, t]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="mx-4 w-full max-w-lg rounded-xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-800">{t("addItem")}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {/* 商品搜索 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("searchProduct")}</label>
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSelectedProduct(null); }}
                placeholder={t("searchPlaceholder")}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              {searching && (
                <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />
              )}
              {showDropdown && results.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                  {results.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectProduct(p)}
                      className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                    >
                      <div>
                        <p className="font-medium text-gray-800">{p.name}</p>
                        <p className="text-xs text-gray-400">{p.spu_code} · {p.category_name}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {showDropdown && results.length === 0 && !searching && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg">
                  <p className="px-3 py-2.5 text-sm text-gray-400">{t("noSearchResult")}</p>
                </div>
              )}
            </div>
          </div>

          {/* 选中商品后：变体 + 数量 + 备注 */}
          {selectedProduct && (
            <>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                </div>
              ) : (
                selectableAttrs.length > 0 && (
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-500">{t("skuSpec")}</label>
                    <VariantSelector
                      selectableAttrs={selectableAttrs}
                      selected={selectedVariants}
                      onChange={handleVariantChange}
                    />
                  </div>
                )
              )}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("quantity")}</label>
                <input
                  type="number"
                  min={0.001}
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("remark")}</label>
                <textarea
                  rows={2}
                  value={remark}
                  onChange={(e) => setRemark(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 border-t border-gray-100 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            {tCommon("cancel")}
          </button>
          <button
            type="button"
            onClick={handleAdd}
            disabled={!selectedProduct}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
          >
            {tCommon("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- 主页面内容 ----------

function CreateOnBehalfContent() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("rfq");
  const tCommon = useTranslations("common");
  const tError = useTranslations("error");
  const toast = useToast();

  // ① 买方组织
  const [buyerQuery, setBuyerQuery] = useState("");
  const [buyerSearching, setBuyerSearching] = useState(false);
  const [buyerResults, setBuyerResults] = useState<BuyerOrgBrief[]>([]);
  const [showBuyerDropdown, setShowBuyerDropdown] = useState(false);
  const [selectedBuyerOrg, setSelectedBuyerOrg] = useState<BuyerOrgBrief | null>(null);
  const buyerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const buyerInputRef = useRef<HTMLInputElement>(null);

  // ② 商品清单
  const [items, setItems] = useState<LocalItem[]>([]);
  const [addItemOpen, setAddItemOpen] = useState(false);

  // ③ 交货信息
  const [deliveryPlace, setDeliveryPlace] = useState("");
  const [destinationPort, setDestinationPort] = useState("");
  const [preferredTradeTerm, setPreferredTradeTerm] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [targetCurrency, setTargetCurrency] = useState("");

  // ④ 联系人
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  // ⑤ 备注
  const [remark, setRemark] = useState("");

  // 提交状态
  const [submitting, setSubmitting] = useState(false);

  // 买方组织防抖搜索
  useEffect(() => {
    if (!buyerQuery.trim()) {
      setBuyerResults([]);
      setShowBuyerDropdown(false);
      return;
    }
    if (buyerTimer.current) clearTimeout(buyerTimer.current);
    buyerTimer.current = setTimeout(async () => {
      setBuyerSearching(true);
      try {
        const res = await searchBuyerOrgs(buyerQuery.trim(), 1, 10);
        setBuyerResults(res.items);
        setShowBuyerDropdown(true);
      } catch {
        setBuyerResults([]);
      } finally {
        setBuyerSearching(false);
      }
    }, 300);
    return () => { if (buyerTimer.current) clearTimeout(buyerTimer.current); };
  }, [buyerQuery]);

  // 选中买方组织
  const handleSelectBuyerOrg = useCallback((org: BuyerOrgBrief) => {
    setSelectedBuyerOrg(org);
    setBuyerQuery("");
    setShowBuyerDropdown(false);
    setBuyerResults([]);
  }, []);

  // 去除选中的买方组织
  const handleClearBuyerOrg = useCallback(() => {
    setSelectedBuyerOrg(null);
    setTimeout(() => buyerInputRef.current?.focus(), 0);
  }, []);

  // 添加行项
  const handleAddItem = useCallback((item: LocalItem) => {
    setItems((prev) => [...prev, item]);
  }, []);

  // 删除行项
  const handleRemoveItem = useCallback((dedupeKey: string) => {
    setItems((prev) => prev.filter((i) => i.dedupeKey !== dedupeKey));
  }, []);

  const existingKeys = new Set(items.map((i) => i.dedupeKey));

  // 表单校验
  const validate = useCallback((): boolean => {
    if (!selectedBuyerOrg) {
      toast.error(t("buyerOrgRequired"));
      return false;
    }
    if (items.length === 0) {
      toast.error(t("itemsRequired"));
      return false;
    }
    return true;
  }, [selectedBuyerOrg, items, toast, t]);

  // 提交（草稿 or 直接提交）
  const handleSubmit = useCallback(async (asDraft: boolean) => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const result = await createRfq({
        buyer_org_id: selectedBuyerOrg!.id,
        as_draft: asDraft,
        items: items.map((item) => ({
          product_id: item.product_id,
          selected_variants: item.selected_variants.length > 0 ? item.selected_variants : undefined,
          quantity: item.quantity,
          remark: item.remark || undefined,
        })),
        requested_delivery_place: deliveryPlace.trim() || undefined,
        destination_port: destinationPort.trim() || undefined,
        preferred_trade_term: preferredTradeTerm.trim() || undefined,
        expected_delivery_date: deliveryDate || undefined,
        target_currency: targetCurrency.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        contact_phone: contactPhone.trim() || undefined,
        contact_email: contactEmail.trim() || undefined,
        remark: remark.trim() || undefined,
      });
      toast.success(asDraft ? t("draftSaved") : t("createSuccess"));
      router.push(`/${locale}/operator/rfqs/${result.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.messageKey) {
        const key = err.messageKey.replace(/^error\./, "");
        try { toast.error(tError(key as Parameters<typeof tError>[0])); } catch { toast.error(err.message); }
      } else {
        toast.error(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    validate, selectedBuyerOrg, items, deliveryPlace, destinationPort, preferredTradeTerm,
    deliveryDate, targetCurrency, contactName, contactPhone, contactEmail, remark,
    router, locale, toast, t, tError,
  ]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* 页头 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-xl font-bold text-gray-800">{t("createOnBehalf")}</h1>
      </div>

      {/* ① 买方组织 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("selectBuyerOrg")}</h2>
        {selectedBuyerOrg ? (
          /* 已选 chip */
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700">
            <span>{selectedBuyerOrg.name}</span>
            {selectedBuyerOrg.code && (
              <span className="text-xs text-blue-400">({selectedBuyerOrg.code})</span>
            )}
            <button
              type="button"
              onClick={handleClearBuyerOrg}
              className="rounded-full p-0.5 text-blue-400 hover:bg-blue-100 hover:text-blue-600 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          /* 搜索输入 */
          <div className="relative">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                ref={buyerInputRef}
                type="text"
                value={buyerQuery}
                onChange={(e) => setBuyerQuery(e.target.value)}
                onFocus={() => { if (buyerResults.length > 0) setShowBuyerDropdown(true); }}
                onBlur={() => setTimeout(() => setShowBuyerDropdown(false), 150)}
                placeholder={t("searchBuyerOrg")}
                className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              {buyerSearching && (
                <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-gray-400" />
              )}
            </div>
            {showBuyerDropdown && buyerResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                {buyerResults.map((org) => (
                  <button
                    key={org.id}
                    type="button"
                    onMouseDown={() => handleSelectBuyerOrg(org)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                  >
                    <span className="font-medium text-gray-800">{org.name}</span>
                    {org.code && <span className="text-xs text-gray-400">{org.code}</span>}
                  </button>
                ))}
              </div>
            )}
            {showBuyerDropdown && buyerResults.length === 0 && !buyerSearching && buyerQuery.trim() && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg">
                <p className="px-3 py-2.5 text-sm text-gray-400">{t("noSearchResult")}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ② 商品清单 */}
      <div className="rounded-xl border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-700">{t("section_items")}</h2>
          <button
            type="button"
            onClick={() => setAddItemOpen(true)}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("addItem")}
          </button>
        </div>
        {items.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            {t("itemsRequired")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-5 py-2.5 font-medium">{t("productName")}</th>
                  <th className="px-5 py-2.5 font-medium">{t("skuSpec")}</th>
                  <th className="px-5 py-2.5 font-medium text-right">{t("quantity")}</th>
                  <th className="px-5 py-2.5 font-medium text-right">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.dedupeKey} className="border-t border-gray-100 even:bg-slate-50/50">
                    <td className="px-5 py-3 font-medium text-gray-800">{item.product_name}</td>
                    <td className="px-5 py-3 text-gray-500">{item.variant_display || "—"}</td>
                    <td className="px-5 py-3 text-right font-semibold text-gray-800">{item.quantity}</td>
                    <td className="px-5 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(item.dedupeKey)}
                        className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
                        title={t("deleteItem")}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ③ 交货信息 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">
          {t("section_delivery")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("deliveryPlace")}</label>
            <input
              type="text"
              value={deliveryPlace}
              onChange={(e) => setDeliveryPlace(e.target.value)}
              placeholder={t("deliveryPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("deliveryDate")}</label>
            <input
              type="date"
              lang={locale}
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("currency")}</label>
            <select
              value={targetCurrency}
              onChange={(e) => setTargetCurrency(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="">—</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
              <option value="TZS">TZS</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("destinationPort")}</label>
            <input
              type="text"
              list="op-destination-port-options"
              value={destinationPort}
              onChange={(e) => setDestinationPort(e.target.value)}
              placeholder={t("destinationPortPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            <datalist id="op-destination-port-options">
              <option value="Dar es Salaam Port" />
              <option value="Mombasa Port" />
              <option value="Zanzibar Port" />
              <option value="Tanga Port" />
            </datalist>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("preferredTradeTerm")}</label>
            <input
              type="text"
              list="op-trade-term-options"
              value={preferredTradeTerm}
              onChange={(e) => setPreferredTradeTerm(e.target.value)}
              placeholder={t("preferredTradeTermPlaceholder")}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            <datalist id="op-trade-term-options">
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

      {/* ④ 联系人 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">
          {t("section_contact")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactName")}</label>
            <input
              type="text"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactPhone")}</label>
            <input
              type="text"
              value={contactPhone}
              onChange={(e) => setContactPhone(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">{t("contactEmail")}</label>
            <input
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* ⑤ 备注 */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">
          {t("remark")}
          <span className="ml-1.5 text-xs font-normal text-gray-400">（选填）</span>
        </h2>
        <textarea
          rows={3}
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* 底部操作栏 */}
      <div className="flex justify-end gap-3 pb-8">
        <button
          type="button"
          onClick={() => router.back()}
          disabled={submitting}
          className="rounded-lg border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
        >
          {tCommon("cancel")}
        </button>
        <button
          type="button"
          onClick={() => handleSubmit(true)}
          disabled={submitting}
          className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("saveDraft")}
        </button>
        <button
          type="button"
          onClick={() => handleSubmit(false)}
          disabled={submitting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-60"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("submitDirectly")}
        </button>
      </div>

      {/* 添加商品弹窗 */}
      {addItemOpen && (
        <AddItemModal
          existingKeys={existingKeys}
          onClose={() => setAddItemOpen(false)}
          onAdd={handleAddItem}
        />
      )}
    </div>
  );
}

export default function CreateOnBehalfPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.RFQ_CLAIM]}>
      <CreateOnBehalfContent />
    </RouteGuard>
  );
}
