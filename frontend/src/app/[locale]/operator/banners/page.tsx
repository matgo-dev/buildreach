"use client";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Plus, X, Upload } from "lucide-react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { ApiError } from "@/lib/api";
import { Permissions } from "@/lib/permissions";
import { imageUrl } from "@/lib/env";
import {
  operatorBannersApi,
  type BannerAdmin,
  type BannerWriteInput,
} from "@/lib/api/operatorBanners";

function Inner() {
  const [rows, setRows] = useState<BannerAdmin[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<BannerAdmin | null>(null);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const showToast = (kind: "ok" | "err", text: string) => {
    setToast({ kind, text });
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await operatorBannersApi.list("home_carousel"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载轮播图失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onDelete = async (b: BannerAdmin) => {
    if (!confirm(`确定删除这张轮播图?\n${b.title_zh || b.image_url}\n删除后首页立即不再展示。`)) return;
    setBusyId(b.id);
    try {
      await operatorBannersApi.remove(b.id);
      await load();
      showToast("ok", "已删除");
    } catch (e) {
      showToast("err", e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setBusyId(null);
    }
  };

  const onToggleActive = async (b: BannerAdmin) => {
    setBusyId(b.id);
    try {
      await operatorBannersApi.update(b.id, { is_active: !b.is_active });
      await load();
      showToast("ok", b.is_active ? "已下架" : "已上架");
    } catch (e) {
      showToast("err", e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">首页轮播图</h1>
          <p className="mt-1 text-sm text-slate-500">
            管理首页顶部轮播图。按「排序」升序播放;下架的不展示。图片建议宽幅横图(如 1600×640)。
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex h-10 items-center gap-2 rounded-lg bg-[#003366] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#002244]"
        >
          <Plus className="h-4 w-4" /> 新增轮播图
        </button>
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">预览</th>
              <th className="px-4 py-3 text-left font-semibold">标题</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">排序</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">跳转链接</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">状态</th>
              <th className="px-4 py-3 text-left font-semibold whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  <Loader2 className="inline h-4 w-4 animate-spin" /> 加载中…
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  暂无轮播图,点右上角新增
                </td>
              </tr>
            )}
            {!loading &&
              rows.map((b) => (
                <tr key={b.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <img
                      src={imageUrl(b.image_full_url || b.image_url)}
                      alt={b.title_zh || ""}
                      className="h-12 w-24 rounded object-cover ring-1 ring-slate-200"
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-800">
                    {b.title_zh || <span className="text-slate-300">(无标题)</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-600">{b.sort_order}</td>
                  <td className="px-4 py-3 max-w-[200px] truncate text-slate-500">
                    {b.link_url || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        "rounded px-2 py-0.5 text-xs font-medium " +
                        (b.is_active
                          ? "bg-emerald-50 text-emerald-600"
                          : "bg-slate-100 text-slate-400")
                      }
                    >
                      {b.is_active ? "已上架" : "已下架"}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <button
                        disabled={busyId === b.id}
                        onClick={() => onToggleActive(b)}
                        className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {b.is_active ? "下架" : "上架"}
                      </button>
                      <button
                        onClick={() => setEditing(b)}
                        className="rounded border border-[#003366]/40 px-2.5 py-1 text-xs font-medium text-[#003366] hover:bg-[#003366]/5"
                      >
                        编辑
                      </button>
                      <button
                        disabled={busyId === b.id}
                        onClick={() => onDelete(b)}
                        className="rounded border border-red-300 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {toast && (
        <div
          className={
            "fixed bottom-6 right-6 flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg " +
            (toast.kind === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
          }
        >
          {toast.kind === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {toast.text}
        </div>
      )}

      {(creating || editing) && (
        <BannerModal
          banner={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={async (msg) => {
            setCreating(false);
            setEditing(null);
            await load();
            showToast("ok", msg);
          }}
        />
      )}
    </div>
  );
}

function BannerModal({
  banner,
  onClose,
  onSaved,
}: {
  banner: BannerAdmin | null;
  onClose: () => void;
  onSaved: (msg: string) => Promise<void>;
}) {
  const isEdit = banner !== null;
  const [titleZh, setTitleZh] = useState(banner?.title_zh ?? "");
  const [titleEn, setTitleEn] = useState(banner?.title_en ?? "");
  const [titleSw, setTitleSw] = useState(banner?.title_sw ?? "");
  const [linkUrl, setLinkUrl] = useState(banner?.link_url ?? "");
  const [sortOrder, setSortOrder] = useState<number>(banner?.sort_order ?? 0);
  const [isActive, setIsActive] = useState<boolean>(banner?.is_active ?? true);
  // 图片:imageKey 提交用,previewUrl 显示用
  const [imageKey, setImageKey] = useState<string>(banner?.image_url ?? "");
  const [previewUrl, setPreviewUrl] = useState<string>(
    banner ? imageUrl(banner.image_full_url || banner.image_url) : "",
  );
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // 允许重复选同一文件
    if (!file) return;
    setErr("");
    setUploading(true);
    try {
      const res = await operatorBannersApi.uploadImage(file);
      setImageKey(res.image_url);
      setPreviewUrl(imageUrl(res.full_url));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "图片上传失败");
    } finally {
      setUploading(false);
    }
  };

  const onSubmit = async () => {
    if (!imageKey) {
      setErr("请先上传图片");
      return;
    }
    setSubmitting(true);
    setErr("");
    const payload: BannerWriteInput = {
      title_zh: titleZh.trim() || null,
      title_en: titleEn.trim() || null,
      title_sw: titleSw.trim() || null,
      link_url: linkUrl.trim() || null,
      sort_order: sortOrder,
      is_active: isActive,
      image_url: imageKey,
      position: "home_carousel",
    };
    try {
      if (isEdit && banner) {
        await operatorBannersApi.update(banner.id, payload);
        await onSaved("已保存");
      } else {
        await operatorBannersApi.create(payload);
        await onSaved("已新增");
      }
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "保存失败");
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[88vh] w-full max-w-lg flex-col rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            {isEdit ? "编辑轮播图" : "新增轮播图"}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          {/* 图片上传 */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">
              图片 <span className="text-red-500">*</span>
            </label>
            <div className="flex items-start gap-3">
              <div className="relative h-24 w-48 shrink-0 overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200">
                {previewUrl ? (
                  <img src={previewUrl} alt="预览" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-slate-400">
                    暂无图片
                  </div>
                )}
                {uploading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Loader2 className="h-5 w-5 animate-spin text-white" />
                  </div>
                )}
              </div>
              <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                <Upload className="h-4 w-4" />
                {previewUrl ? "更换图片" : "上传图片"}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={onPickFile}
                  disabled={uploading}
                />
              </label>
            </div>
          </div>

          {/* 标题 */}
          <div className="grid grid-cols-1 gap-3">
            <Field label="标题(中)" value={titleZh} onChange={setTitleZh} placeholder="可留空,纯展示图无需文字" />
            <div className="grid grid-cols-2 gap-3">
              <Field label="标题(英)" value={titleEn} onChange={setTitleEn} placeholder="可选" />
              <Field label="标题(斯瓦希里)" value={titleSw} onChange={setTitleSw} placeholder="可选" />
            </div>
          </div>

          {/* 链接 */}
          <Field
            label="跳转链接"
            value={linkUrl}
            onChange={setLinkUrl}
            placeholder="点击轮播图跳转的路径,如 /mall(可选)"
          />

          {/* 排序 + 状态 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-600">排序(小在前)</label>
              <input
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(Number(e.target.value))}
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm text-slate-800 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-600">状态</label>
              <label className="flex h-10 items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300"
                />
                上架展示
              </label>
            </div>
          </div>

          {err && (
            <div className="flex items-center gap-2 rounded-md border-l-4 border-red-500 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="h-4 w-4" /> {err}
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="h-10 rounded-lg border border-slate-300 px-4 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            取消
          </button>
          <button
            onClick={onSubmit}
            disabled={submitting || uploading}
            className="flex h-10 items-center gap-2 rounded-lg bg-[#003366] px-5 text-sm font-semibold text-white hover:bg-[#002244] disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-600">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm text-slate-800 placeholder-slate-400 focus:border-[#003366] focus:outline-none focus:ring-2 focus:ring-[#003366]/15"
      />
    </div>
  );
}

export default function Page() {
  return (
    <RouteGuard requiredPermissions={[Permissions.BANNER_READ]}>
      <Inner />
    </RouteGuard>
  );
}
