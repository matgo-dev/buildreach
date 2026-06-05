"use client";

export interface Column<T> {
  key: string;
  title: string;
  width?: string;
  align?: "left" | "center" | "right";
  render: (row: T, index: number) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyText?: string;
  onRowClick?: (row: T) => void;
  rowKey: (row: T) => string | number;
}

/**
 * 运营后台通用数据表格。
 * 对标截图：表头灰底、交替行底色、hover 蓝色高亮、行可点击。
 */
export function DataTable<T>({
  columns,
  data,
  loading,
  emptyText = "暂无数据",
  onRowClick,
  rowKey,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-[12px] font-semibold text-slate-600 ${
                  col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""
                }`}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-16 text-center text-slate-400">
                加载中...
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-16 text-center text-slate-400">
                {emptyText}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-slate-100 transition-colors ${
                  onRowClick ? "cursor-pointer hover:bg-blue-50/50" : ""
                } ${idx % 2 === 1 ? "bg-slate-50/40" : ""}`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 ${
                      col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""
                    }`}
                  >
                    {col.render(row, idx)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

/** 通用分页组件 */
export function Pagination({
  page,
  pages,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPageChange: (p: number) => void;
}) {
  if (pages <= 1) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-3">
      <p className="text-[12px] text-slate-500">
        显示 {start}-{end} / 共 {total} 条
      </p>
      <div className="flex items-center gap-1">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-[12px] text-slate-600 hover:bg-slate-50 disabled:opacity-40"
        >
          上一页
        </button>
        {Array.from({ length: Math.min(pages, 7) }, (_, i) => i + 1).map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`rounded-md px-3 py-1.5 text-[12px] font-medium ${
              p === page
                ? "bg-blue-600 text-white"
                : "border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {p}
          </button>
        ))}
        <button
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-[12px] text-slate-600 hover:bg-slate-50 disabled:opacity-40"
        >
          下一页
        </button>
      </div>
    </div>
  );
}
