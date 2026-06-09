"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { AlertCircle, Loader2, Package, Plus, Search } from "lucide-react";

import Pagination from "@/components/ui/Pagination";
import { CategoryCascaderDropdown } from "@/components/category/CategoryCascaderDropdown";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { useToast } from "@/components/ui/Toast";
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


// ---------- 格式化 ----------

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatPrice(min: number | null, max: number | null, currency?: string | null): string | null {
  if (min == null && max == null) return null;
  const suffix = currency ? ` ${currency}` : "";
  if (min != null && max != null) {
    if (min === max) return Number(min).toLocaleString() + suffix;
    return `${Number(min).toLocaleString()} - ${Number(max).toLocaleString()}${suffix}`;
  }
  const val = min ?? max;
  return Number(val).toLocaleString() + suffix;
}

// ---------- 可排序表头 ----------

function SortableHeader({
  label,
  field,
  sortBy,
  sortOrder,
  onSort,
  align = "left",
}: {
  label: string;
  field: string;
  sortBy: string | null;
  sortOrder: "asc" | "desc";
  onSort: (field: string) => void;
  align?: "left" | "right" | "center";
}) {
  const active = sortBy === field;
  const alignCls = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  const justifyCls = align === "right" ? "justify-end" : align === "center" ? "justify-center" : "justify-start";
  return (
    <th
      className={`px-4 py-3 ${alignCls} font-semibold whitespace-nowrap cursor-pointer select-none hover:bg-slate-100 transition-colors`}
      onClick={() => onSort(field)}
    >
      <span className={`inline-flex items-center gap-1 ${justifyCls}`}>
        {label}
        <span className={`text-xs ${active ? "text-blue-600" : "text-slate-300"}`}>
          {active ? (sortOrder === "asc" ? "\u25B2" : "\u25BC") : "\u21C5"}
        </span>
      </span>
    </th>
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

  // 排序（后端暂不支持，客户端排序）
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // 批量选择
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  // 弹窗 / Toast
  const [confirmState, setConfirmState] = useState<{
    type: "publish" | "unpublish" | "delete";
    item: ProductOperatorItem;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const { success: toastSuccess } = useToast();

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

  // ---------- 客户端排序 ----------
  const handleSort = useCallback((field: string) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  }, [sortBy]);

  const sortedItems = useMemo(() => {
    if (!sortBy) return items;
    const sorted = [...items].sort((a, b) => {
      let va: number | null = null;
      let vb: number | null = null;
      if (sortBy === "updated_at") {
        va = a.updated_at ? new Date(a.updated_at).getTime() : null;
        vb = b.updated_at ? new Date(b.updated_at).getTime() : null;
      } else if (sortBy === "price_min") {
        va = a.price_min;
        vb = b.price_min;
      } else if (sortBy === "sku_count") {
        va = a.sku_count;
        vb = b.sku_count;
      }
      // null 值排最后
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return sortOrder === "asc" ? va - vb : vb - va;
    });
    return sorted;
  }, [items, sortBy, sortOrder]);

  // ---------- 行内操作 ----------
  const handleAction = useCallback(
    async () => {
      if (!confirmState) return;
      setActionLoading(true);
      try {
        const { type, item } = confirmState;
        if (type === "publish") {
          await operatorProductsApi.updateStatus(item.id, { status: "ACTIVE" });
          toastSuccess(t("toastPublished"));
        } else if (type === "unpublish") {
          await operatorProductsApi.updateStatus(item.id, { status: "INACTIVE" });
          toastSuccess(t("toastUnpublished"));
        } else if (type === "delete") {
          await operatorProductsApi.remove(item.id);
          toastSuccess(t("toastDeleted"));
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

  // 批量上架（走正常校验）
  const handleBatchPublish = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    setError("");
    let successCount = 0;
    const errors: string[] = [];
    for (const id of selectedIds) {
      try {
        await operatorProductsApi.updateStatus(id, { status: "ACTIVE" });
        successCount++;
      } catch (e) {
        const name = items.find((i) => i.id === id)?.name ?? String(id);
        errors.push(`${name}: ${e instanceof ApiError ? e.message : "failed"}`);
      }
    }
    setBatchLoading(false);
    setSelectedIds(new Set());
    if (successCount > 0) {
      toastSuccess(t("batchPublishSuccess", { count: successCount }));
      void load(page);
    }
    if (errors.length > 0) {
      setError(errors.join("; "));
    }
  }, [selectedIds, items, page, load, t]);

  const confirmConfig = useMemo(() => {
    if (!confirmState) return null;
    const { type, item } = confirmState;
    switch (type) {
      case "publish":
        return {
          title: t("confirmPublishTitle"),
          message: t("confirmPublishMsg", { name: item.name }),
          confirmLabel: t("confirmPublishBtn"),
        };
      case "unpublish":
        return {
          title: t("confirmUnpublishTitle"),
          message: t("confirmUnpublishMsg", { name: item.name }),
          confirmLabel: t("confirmUnpublishBtn"),
        };
      case "delete":
        return {
          title: t("confirmDeleteTitle"),
          message: t("confirmDeleteMsg", { name: item.name }),
          confirmLabel: t("confirmDeleteBtn"),
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
        <div className="relative w-[280px] shrink-0">
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

        <CategoryCascaderDropdown
          tree={categoryTree}
          value={categoryCode}
          onChange={setCategoryCode}
          placeholder={t("allCategories")}
        />

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
            {t("batchSelected", { count: selectedIds.size })}
          </span>
          <button
            onClick={() => void handleBatchPublish()}
            disabled={batchLoading}
            className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {batchLoading && <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />}
            {t("batchPublish")}
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-sm text-blue-600 hover:underline"
          >
            {t("batchCancel")}
          </button>
        </div>
      )}

      {/* 表格 */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-[1100px] w-full text-sm">
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
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">{t("colProductInfo")}</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">{t("colSpuCode")}</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">{t("colCategory")}</th>
              <SortableHeader label={t("colPrice")} field="price_min" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} align="right" />
              <SortableHeader label={t("colSkuCount")} field="sku_count" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} align="center" />
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">{t("colStatus")}</th>
              <SortableHeader label={t("colUpdatedAt")} field="updated_at" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />
              <th className="px-4 py-3 text-right font-semibold whitespace-nowrap">{t("colActions")}</th>
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
              sortedItems.map((item) => {
                const statusStyle = STATUS_STYLES[item.status] ?? STATUS_STYLES.DRAFT;
                const priceText = formatPrice(item.price_min, item.price_max, item.currency);
                const catName = resolveCategoryName(item.category_code, catMap);

                return (
                  <tr
                    key={item.id}
                    className="even:bg-slate-50/50 hover:bg-blue-50/50 transition-colors cursor-pointer"
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
                          <p className="truncate font-medium text-slate-900 max-w-[280px]">{item.name}</p>
                          {item.created_by_name && (
                            <p className="truncate text-xs text-slate-400">{item.created_by_name}</p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono text-xs text-slate-600">{item.spu_code}</td>

                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{catName}</td>

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
        <Pagination
          current={page}
          total={pages}
          totalItems={total}
          onChange={(p) => void load(p)}
        />
      )}

      {/* 确认弹窗 */}
      <ConfirmModal
        open={!!confirmConfig}
        title={confirmConfig?.title ?? ""}
        description={confirmConfig?.message}
        confirmLabel={confirmConfig?.confirmLabel}
        cancelLabel={t("cancel")}
        variant={confirmState?.type === "delete" ? "danger" : confirmState?.type === "unpublish" ? "warning" : "primary"}
        loading={actionLoading}
        onConfirm={handleAction}
        onCancel={() => setConfirmState(null)}
      />

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
