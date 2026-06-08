"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { AlertCircle, ChevronLeft, ChevronRight, Loader2, Package, Plus, Search } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { usePermissions } from "@/hooks/usePermissions";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import {
  operatorProductsApi,
  type ProductListParams,
  type ProductOperatorItem,
} from "@/lib/api/operatorProducts";
import { Permissions } from "@/lib/permissions";
import type { CategoryTreeNode } from "@/lib/api/categories";

const PAGE_SIZE = 20;

// 状态配色(i18n label 从 t() 取)
const STATUS_STYLES: Record<string, { dot: string; bg: string; text: string; key: string }> = {
  DRAFT:    { dot: "bg-amber-400",   bg: "bg-amber-50",   text: "text-amber-700",   key: "statusDraft" },
  ACTIVE:   { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", key: "statusActive" },
  INACTIVE: { dot: "bg-slate-400",   bg: "bg-slate-100",  text: "text-slate-600",   key: "statusInactive" },
};

// ---------- 品类名称链解析 ----------

function buildCategoryMap(nodes: CategoryTreeNode[], map: Map<string, CategoryTreeNode> = new Map()) {
  for (const n of nodes) {
    map.set(n.code, n);
    if (n.children?.length) buildCategoryMap(n.children, map);
  }
  return map;
}

function resolveCategoryName(code: string, catMap: Map<string, CategoryTreeNode>): string {
  const node = catMap.get(code);
  if (!node) return code;
  return node.name;
}

function collectLeafNodes(nodes: CategoryTreeNode[]): { code: string; name: string }[] {
  const leaves: { code: string; name: string }[] = [];
  function walk(ns: CategoryTreeNode[], ancestors: string[] = []) {
    for (const n of ns) {
      if (n.children?.length) {
        walk(n.children, [...ancestors, n.name]);
      } else {
        const path = [...ancestors, n.name].join(" > ");
        leaves.push({ code: n.code, name: path });
      }
    }
  }
  walk(nodes);
  return leaves;
}

// ---------- 格式化 ----------

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatPrice(min: number | null, max: number | null, currency: string | null): string | null {
  if (min == null && max == null) return null;
  const c = currency ?? "TZS";
  if (min != null && max != null) {
    if (min === max) return `${c} ${Number(min).toLocaleString()}`;
    return `${c} ${Number(min).toLocaleString()} - ${Number(max).toLocaleString()}`;
  }
  const val = min ?? max;
  return `${c} ${Number(val).toLocaleString()}`;
}

// ---------- 确认弹窗 ----------

function ConfirmDialog({
  open, title, message, confirmLabel, cancelLabel, confirmColor, loading, onConfirm, onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  confirmColor?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        <p className="mt-2 text-sm text-slate-600 whitespace-pre-wrap">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${confirmColor ?? "bg-blue-600 hover:bg-blue-700"}`}
          >
            {loading && <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- Toast ----------

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-slate-800 px-4 py-3 text-sm text-white shadow-lg">
      {message}
    </div>
  );
}

// ===================== 主页面 =====================

function ProductListInner() {
  const t = useTranslations("productList");
  const router = useRouter();
  const locale = useLocale();
  const { hasPermission } = usePermissions();
  const { tree: categoryTree } = useCategoryTree();

  const catMap = useMemo(() => buildCategoryMap(categoryTree), [categoryTree]);
  const leafCategories = useMemo(() => collectLeafNodes(categoryTree), [categoryTree]);

  // 列表数据
  const [items, setItems] = useState<ProductOperatorItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 筛选
  const [keyword, setKeyword] = useState("");
  const [categoryCode, setCategoryCode] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // 批量选择
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  // 弹窗 / Toast
  const [confirmState, setConfirmState] = useState<{
    type: "publish" | "unpublish" | "delete";
    item: ProductOperatorItem;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [toast, setToast] = useState("");

  const canWrite = hasPermission(Permissions.PRODUCT_WRITE);
  const canApprove = hasPermission(Permissions.PRODUCT_APPROVE);

  const load = useCallback(
    async (p = 1) => {
      setLoading(true);
      setError("");
      try {
        const params: ProductListParams = { page: p, size: PAGE_SIZE };
        if (keyword.trim()) params.keyword = keyword.trim();
        if (categoryCode) params.category_code = categoryCode;
        if (statusFilter) params.status = statusFilter;

        const data = await operatorProductsApi.list(params);
        setItems(data.items);
        setTotal(data.total);
        setPage(data.page);
        setPages(data.pages);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("loadError"));
      } finally {
        setLoading(false);
      }
    },
    [keyword, categoryCode, statusFilter, t]
  );

  // 初始加载 + 筛选变更自动重载（回第 1 页）
  const isFirstRender = useMemo(() => ({ current: true }), []);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      void load(1);
      return;
    }
    void load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryCode, statusFilter]);

  // ---------- 行内操作 ----------
  const handleAction = useCallback(
    async () => {
      if (!confirmState) return;
      setActionLoading(true);
      try {
        const { type, item } = confirmState;
        if (type === "publish") {
          await operatorProductsApi.updateStatus(item.id, { status: "ACTIVE" });
          setToast(t("toastPublished"));
        } else if (type === "unpublish") {
          await operatorProductsApi.updateStatus(item.id, { status: "INACTIVE" });
          setToast(t("toastUnpublished"));
        } else if (type === "delete") {
          await operatorProductsApi.remove(item.id);
          setToast(t("toastDeleted"));
        }
        setConfirmState(null);
        void load(type === "delete" && items.length === 1 && page > 1 ? page - 1 : page);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("actionError"));
        setConfirmState(null);
      } finally {
        setActionLoading(false);
      }
    },
    [confirmState, items.length, page, load, t]
  );

  // 批量上架(跳过校验)
  const handleBatchPublish = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    setError("");
    let successCount = 0;
    const errors: string[] = [];
    for (const id of selectedIds) {
      try {
        await operatorProductsApi.updateStatus(id, { status: "ACTIVE" }, true);
        successCount++;
      } catch (e) {
        const name = items.find((i) => i.id === id)?.name ?? String(id);
        errors.push(`${name}: ${e instanceof ApiError ? e.message : "failed"}`);
      }
    }
    setBatchLoading(false);
    setSelectedIds(new Set());
    if (successCount > 0) {
      setToast(`${successCount} 件商品已上架`);
      void load(page);
    }
    if (errors.length > 0) {
      setError(errors.join("; "));
    }
  }, [selectedIds, items, page, load]);

  const confirmConfig = useMemo(() => {
    if (!confirmState) return null;
    const { type, item } = confirmState;
    switch (type) {
      case "publish":
        return {
          title: t("confirmPublishTitle"),
          message: t("confirmPublishMsg", { name: item.name }),
          confirmLabel: t("confirmPublishBtn"),
          confirmColor: "bg-emerald-600 hover:bg-emerald-700",
        };
      case "unpublish":
        return {
          title: t("confirmUnpublishTitle"),
          message: t("confirmUnpublishMsg", { name: item.name }),
          confirmLabel: t("confirmUnpublishBtn"),
          confirmColor: "bg-amber-600 hover:bg-amber-700",
        };
      case "delete":
        return {
          title: t("confirmDeleteTitle"),
          message: t("confirmDeleteMsg", { name: item.name }),
          confirmLabel: t("confirmDeleteBtn"),
          confirmColor: "bg-red-600 hover:bg-red-700",
        };
      default:
        return null;
    }
  }, [confirmState, t]);

  const hasFilters = keyword.trim() || categoryCode || statusFilter;

  return (
    <div className="space-y-5">
      {/* 顶部 */}
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-slate-500">{t("subtitle")}</p>
        </div>
        {canWrite && (
          <Link
            href="/operator/products/create"
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("createProduct")}
          </Link>
        )}
      </header>

      {/* 筛选区 */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(1)}
            placeholder={t("searchPlaceholder")}
            className="h-10 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-700 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        <select
          value={categoryCode}
          onChange={(e) => setCategoryCode(e.target.value)}
          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("allCategories")}</option>
          {leafCategories.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("allStatus")}</option>
          <option value="DRAFT">{t("statusDraft")}</option>
          <option value="ACTIVE">{t("statusActive")}</option>
          <option value="INACTIVE">{t("statusInactive")}</option>
        </select>

        <button
          onClick={() => void load(1)}
          className="h-10 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700"
        >
          {t("search")}
        </button>

        <span className="ml-auto text-sm text-slate-500">
          {t("totalCount", { count: total })}
        </span>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
          <button onClick={() => setError("")} className="ml-auto text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      {/* 批量操作条 */}
      {canApprove && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
          <span className="text-sm text-blue-700">
            已选 <strong>{selectedIds.size}</strong> 件商品
          </span>
          <button
            onClick={() => void handleBatchPublish()}
            disabled={batchLoading}
            className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {batchLoading && <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />}
            批量上架（跳过校验）
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-sm text-blue-600 hover:underline"
          >
            取消选择
          </button>
        </div>
      )}

      {/* 表格 */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              {canApprove && (
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={items.length > 0 && items.every((i) => selectedIds.has(i.id))}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedIds(new Set(items.map((i) => i.id)));
                      } else {
                        setSelectedIds(new Set());
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                </th>
              )}
              <th className="px-4 py-3 text-left font-semibold">{t("colProductInfo")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("colSpuCode")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("colCategory")}</th>
              <th className="px-4 py-3 text-right font-semibold">{t("colPrice")}</th>
              <th className="px-4 py-3 text-center font-semibold">{t("colSkuCount")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("colStatus")}</th>
              <th className="px-4 py-3 text-left font-semibold">{t("colUpdatedAt")}</th>
              <th className="px-4 py-3 text-right font-semibold">{t("colActions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={canApprove ? 9 : 8} className="px-4 py-16 text-center text-slate-400">
                  <Loader2 className="inline h-5 w-5 animate-spin" />
                  <span className="ml-2">{t("loading")}</span>
                </td>
              </tr>
            )}

            {!loading && items.length === 0 && !hasFilters && (
              <tr>
                <td colSpan={canApprove ? 9 : 8} className="px-4 py-16 text-center">
                  <Package className="mx-auto h-12 w-12 text-slate-300" />
                  <p className="mt-3 text-base font-medium text-slate-500">{t("emptyTitle")}</p>
                  <p className="mt-1 text-sm text-slate-400">{t("emptyHint")}</p>
                  {canWrite && (
                    <Link
                      href="/operator/products/create"
                      className="mt-4 inline-flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                    >
                      <Plus className="h-4 w-4" /> {t("createProduct")}
                    </Link>
                  )}
                </td>
              </tr>
            )}

            {!loading && items.length === 0 && hasFilters && (
              <tr>
                <td colSpan={canApprove ? 9 : 8} className="px-4 py-16 text-center">
                  <Search className="mx-auto h-12 w-12 text-slate-300" />
                  <p className="mt-3 text-base font-medium text-slate-500">{t("noResultTitle")}</p>
                  <p className="mt-1 text-sm text-slate-400">{t("noResultHint")}</p>
                </td>
              </tr>
            )}

            {!loading &&
              items.map((item) => {
                const statusStyle = STATUS_STYLES[item.status] ?? STATUS_STYLES.DRAFT;
                const priceText = formatPrice(item.price_min, item.price_max, item.currency);
                const catName = resolveCategoryName(item.category_code, catMap);

                return (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => router.push(`/${locale}/operator/products/${item.id}`)}
                  >
                    {canApprove && (
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={(e) => {
                            const next = new Set(selectedIds);
                            if (e.target.checked) next.add(item.id);
                            else next.delete(item.id);
                            setSelectedIds(next);
                          }}
                          className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {item.main_image ? (
                          /* eslint-disable-next-line @next/next/no-img-element */
                          <img
                            src={item.main_image}
                            alt={item.name}
                            className="h-11 w-11 rounded-lg object-cover bg-slate-100"
                            onError={(e) => {
                              // 图片加载失败时隐藏 img，显示占位
                              (e.target as HTMLImageElement).style.display = "none";
                              (e.target as HTMLImageElement).nextElementSibling?.classList.remove("hidden");
                            }}
                          />
                        ) : null}
                        <div className={`flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100${item.main_image ? " hidden" : ""}`}>
                          <Package className="h-5 w-5 text-slate-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-slate-900 max-w-[200px]">{item.name}</p>
                          {item.created_by_name && (
                            <p className="truncate text-xs text-slate-400">{item.created_by_name}</p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono text-xs text-slate-600">{item.spu_code}</td>

                    <td className="px-4 py-3 text-slate-600 max-w-[160px] truncate">{catName}</td>

                    <td className="px-4 py-3 text-right">
                      {priceText ? (
                        <span className="text-slate-700">{priceText}</span>
                      ) : (
                        <span className="italic text-slate-400">{t("noPrice")}</span>
                      )}
                    </td>

                    <td className="px-4 py-3 text-center">
                      <span
                        className={`inline-flex min-w-[28px] items-center justify-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          item.sku_count === 0
                            ? "bg-red-50 text-red-600"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {item.sku_count}
                      </span>
                    </td>

                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusStyle.bg} ${statusStyle.text}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
                        {t(statusStyle.key as "statusDraft" | "statusActive" | "statusInactive")}
                      </span>
                    </td>

                    <td className="px-4 py-3 text-xs text-slate-500">{formatTime(item.updated_at)}</td>

                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        {canWrite && (item.status === "DRAFT" || item.status === "INACTIVE") && (
                          <button
                            onClick={(e) => { e.stopPropagation(); router.push(`/${locale}/operator/products/${item.id}?edit=true`); }}
                            className="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50"
                          >
                            {t("edit")}
                          </button>
                        )}
                        {item.status === "DRAFT" && canApprove && (
                          <button
                            onClick={() => setConfirmState({ type: "publish", item })}
                            className="rounded px-2 py-1 text-xs text-emerald-600 hover:bg-emerald-50"
                          >
                            {t("publish")}
                          </button>
                        )}
                        {item.status === "ACTIVE" && canApprove && (
                          <button
                            onClick={() => setConfirmState({ type: "unpublish", item })}
                            className="rounded px-2 py-1 text-xs text-amber-600 hover:bg-amber-50"
                          >
                            {t("unpublish")}
                          </button>
                        )}
                        {item.status === "INACTIVE" && canApprove && (
                          <button
                            onClick={() => setConfirmState({ type: "publish", item })}
                            className="rounded px-2 py-1 text-xs text-emerald-600 hover:bg-emerald-50"
                          >
                            {t("publish")}
                          </button>
                        )}
                        {(item.status === "DRAFT" || item.status === "INACTIVE") && canWrite && (
                          <button
                            onClick={(e) => { e.stopPropagation(); setConfirmState({ type: "delete", item }); }}
                            className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                          >
                            {t("delete")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {pages > 0 && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>{t("pagination", { total, page, pages })}</span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1 || loading}
              onClick={() => void load(page - 1)}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" /> {t("prevPage")}
            </button>
            <button
              disabled={page >= pages || loading}
              onClick={() => void load(page + 1)}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {t("nextPage")} <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* 确认弹窗 */}
      {confirmConfig && (
        <ConfirmDialog
          open
          title={confirmConfig.title}
          message={confirmConfig.message}
          confirmLabel={confirmConfig.confirmLabel}
          cancelLabel={t("cancel")}
          confirmColor={confirmConfig.confirmColor}
          loading={actionLoading}
          onConfirm={handleAction}
          onCancel={() => setConfirmState(null)}
        />
      )}

      {/* Toast */}
      {toast && <Toast message={toast} onClose={() => setToast("")} />}
    </div>
  );
}

export default function OperatorProductListPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.PRODUCT_READ]}>
      <ProductListInner />
    </RouteGuard>
  );
}
