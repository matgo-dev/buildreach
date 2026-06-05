"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Package, CheckCircle2, FileEdit, XCircle, Plus,
  Eye, Pencil, ArrowUpCircle, ArrowDownCircle, Trash2,
} from "lucide-react";

import { operatorProductApi, type ProductOperator, type PageResult } from "@/lib/productApi";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { FilterBar, FilterSelect } from "@/components/admin/FilterBar";
import { DataTable, Pagination, type Column } from "@/components/admin/DataTable";
import { StatCard } from "@/components/products/StatCard";
import { StatusBadge } from "@/components/products/StatusBadge";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8002";
const PAGE_SIZE = 20;

export default function OperatorProductsPage() {
  const router = useRouter();
  const [data, setData] = useState<PageResult<ProductOperator> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await operatorProductApi.list({
        keyword: keyword || undefined,
        status: status || undefined,
        page,
        size: PAGE_SIZE,
      });
      setData(res);
    } catch (e) {
      console.error("Failed to load products", e);
    } finally {
      setLoading(false);
    }
  }, [keyword, status, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const activeCount = items.filter((p) => p.status === "ACTIVE").length;
  const draftCount = items.filter((p) => p.status === "DRAFT").length;
  const inactiveCount = items.filter((p) => p.status === "INACTIVE").length;

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await operatorProductApi.updateStatus(id, newStatus);
      fetchData();
    } catch (e: any) {
      alert(e.message || "操作失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除该草稿商品？")) return;
    try {
      await operatorProductApi.delete(id);
      fetchData();
    } catch (e: any) {
      alert(e.message || "删除失败");
    }
  };

  const columns: Column<ProductOperator>[] = [
    {
      key: "product",
      title: "商品名称 / Product",
      render: (p) => (
        <div className="flex items-center gap-3">
          {p.main_image ? (
            <img src={p.main_image} alt="" className="h-10 w-10 rounded border border-slate-200 object-cover" />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded border border-slate-200 bg-slate-50">
              <Package className="h-5 w-5 text-slate-300" />
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{p.name}</p>
            {p.name_i18n && <p className="truncate text-[11px] text-slate-400">{Object.values(p.name_i18n).filter(Boolean).join(" / ")}</p>}
          </div>
        </div>
      ),
    },
    {
      key: "sku",
      title: "SKU 编码",
      width: "120px",
      render: (p) => <span className="font-mono text-[12px] text-slate-600">{p.sku_code}</span>,
    },
    {
      key: "category",
      title: "品类 / Category",
      width: "100px",
      render: (p) => <span className="text-slate-600">{p.category_code}</span>,
    },
    {
      key: "price",
      title: "价格区间 / Price",
      width: "140px",
      render: (p) => (
        <span className="text-slate-700 font-medium">
          ${Number(p.price_min).toFixed(2)} - ${Number(p.price_max).toFixed(2)}
        </span>
      ),
    },
    {
      key: "moq",
      title: "起订量 / MOQ",
      width: "100px",
      render: (p) => <span className="text-slate-600">{p.moq} {p.unit}</span>,
    },
    {
      key: "suppliers",
      title: "供应商",
      width: "70px",
      align: "center",
      render: (p) => (
        <span className="inline-flex items-center justify-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
          {p.supplier_count}
        </span>
      ),
    },
    {
      key: "status",
      title: "状态",
      width: "80px",
      render: (p) => <StatusBadge status={p.status} />,
    },
    {
      key: "actions",
      title: "操作",
      width: "120px",
      align: "right",
      render: (p) => (
        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <button title="查看" className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => router.push(`products/${p.id}`)}>
            <Eye className="h-4 w-4" />
          </button>
          <button title="编辑" className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => router.push(`products/${p.id}?edit=1`)}>
            <Pencil className="h-4 w-4" />
          </button>
          {p.status === "DRAFT" && (
            <>
              <button title="上架" className="rounded p-1.5 text-emerald-500 hover:bg-emerald-50" onClick={() => handleStatusChange(p.id, "ACTIVE")}>
                <ArrowUpCircle className="h-4 w-4" />
              </button>
              <button title="删除" className="rounded p-1.5 text-red-400 hover:bg-red-50" onClick={() => handleDelete(p.id)}>
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
          {p.status === "ACTIVE" && (
            <button title="下架" className="rounded p-1.5 text-amber-500 hover:bg-amber-50" onClick={() => handleStatusChange(p.id, "INACTIVE")}>
              <ArrowDownCircle className="h-4 w-4" />
            </button>
          )}
          {p.status === "INACTIVE" && (
            <button title="重新上架" className="rounded p-1.5 text-emerald-500 hover:bg-emerald-50" onClick={() => handleStatusChange(p.id, "ACTIVE")}>
              <ArrowUpCircle className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <AdminPageHeader
        titleZh="商品中心"
        titleEn="Product Center"
        subtitle="管理商品目录、SKU 及供应商供货关系"
        breadcrumbs={[{ label: "运营后台", href: "/operator/dashboard" }, { label: "商品中心" }]}
        actions={
          <button
            onClick={() => router.push("products/new")}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-[13px] font-medium text-white shadow-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            新增商品 / Add Product
          </button>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard title="全部商品 / Total" value={total} accentColor="#3B82F6" icon={<Package className="h-5 w-5" />} />
        <StatCard title="已上架 / Active" value={activeCount} accentColor="#10B981" icon={<CheckCircle2 className="h-5 w-5" />} />
        <StatCard title="草稿 / Draft" value={draftCount} accentColor="#F59E0B" icon={<FileEdit className="h-5 w-5" />} />
        <StatCard title="已下架 / Inactive" value={inactiveCount} accentColor="#EF4444" icon={<XCircle className="h-5 w-5" />} />
      </div>

      {/* 筛选 */}
      <FilterBar
        keyword={keyword}
        onKeywordChange={(v) => { setKeyword(v); setPage(1); }}
        searchPlaceholder="搜索商品名称或 SKU..."
      >
        <FilterSelect
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={[
            { value: "", label: "全部状态" },
            { value: "ACTIVE", label: "已上架" },
            { value: "DRAFT", label: "草稿" },
            { value: "INACTIVE", label: "已下架" },
          ]}
        />
      </FilterBar>

      {/* 表格 */}
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        emptyText="暂无商品，点击「新增商品」创建第一个"
        rowKey={(p) => p.id}
        onRowClick={(p) => router.push(`products/${p.id}`)}
      />

      {/* 分页 */}
      {data && (
        <Pagination page={page} pages={data.pages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      )}
    </div>
  );
}
