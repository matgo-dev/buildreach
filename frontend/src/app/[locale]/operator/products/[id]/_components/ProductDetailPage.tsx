"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import useSWR from "swr";
import {
  ArrowLeft, Package, Edit3, TrendingUp, TrendingDown,
  Trash2, ChevronDown, ChevronRight, ChevronLeft, X, Loader2, AlertCircle,
  Plus, Star,
} from "lucide-react";
import Toggle from "@/components/ui/Toggle";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { usePermissions } from "@/hooks/usePermissions";
import { Permissions } from "@/lib/permissions";
import { useCategoryTree } from "@/hooks/useCategoryTree";
import { ApiError } from "@/lib/api";
import {
  operatorProductsApi,
  ProductOperatorDetail,
  SkuOperatorDetail,
  ProductAttrDetail,
  ProductImage,
  PriceTierSchema,
  ProductUpdateInput,
  ProductAttrInput,
  AttrTemplate,
} from "@/lib/api/operatorProducts";
import { useToast } from "@/components/ui/Toast";
import EditBasicInfo from "./EditBasicInfo";
import SkuEditModal, { SkuFormData } from "./SkuEditModal";

// 状态颜色映射（label 通过 t() 读取，不在此硬编码）
const STATUS_STYLES: Record<string, { dot: string; bg: string; text: string; labelKey: string }> = {
  DRAFT: { dot: "bg-amber-400", bg: "bg-amber-50", text: "text-amber-700", labelKey: "statusDraft" },
  ACTIVE: { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", labelKey: "statusActive" },
  INACTIVE: { dot: "bg-slate-400", bg: "bg-slate-100", text: "text-slate-600", labelKey: "statusInactive" },
};

function formatPrice(min: number | null, max: number | null, currency: string | null): string {
  if (min == null && max == null) return "—";
  const c = currency || "TZS";
  const fmt = (v: number) => `${c} ${v.toLocaleString()}`;
  if (min != null && max != null && min !== max) return `${fmt(min)} - ${fmt(max)}`;
  return fmt(min ?? max!);
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${h}:${min}`;
}

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const t = useTranslations("productDetail");
  const tList = useTranslations("productList");
  const tError = useTranslations("error");

  // 将后端 ApiError 的 messageKey 翻译为当前语言，回退到原始 message
  const translateError = useCallback((err: unknown): string => {
    if (err instanceof ApiError && err.messageKey) {
      // messageKey 格式: "error.product.xxx" → tError key: "product.xxx"
      const key = err.messageKey.replace(/^error\./, "");
      try {
        return tError(key, (err.messageParams ?? {}) as Record<string, string>);
      } catch {
        return err.message;
      }
    }
    return err instanceof Error ? err.message : String(err);
  }, [tError]);
  const { hasPermission } = usePermissions();
  const { tree: categoryTree } = useCategoryTree();

  const productId = Number(params.id);
  const startInEdit = searchParams.get("edit") === "true";

  // 数据加载
  const { data: product, error, isLoading, mutate } = useSWR<ProductOperatorDetail>(
    productId ? `operator-product-${productId}` : null,
    () => operatorProductsApi.detail(productId),
    { revalidateOnFocus: false }
  );

  // 编辑态（增量保存：各实体即时落库，不再聚合提交）
  const [isEditing, setIsEditing] = useState(false);
  const [spuForm, setSpuForm] = useState<ProductUpdateInput>({});
  const spuDirtyRef = useRef(false);
  const [skuTemplates, setSkuTemplates] = useState<AttrTemplate[]>([]);
  const [spuSaving, setSpuSaving] = useState(false);
  const [skuSaving, setSkuSaving] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [skuModalOpen, setSkuModalOpen] = useState(false);
  const [skuModalData, setSkuModalData] = useState<{ sku: SkuOperatorDetail | null; isNew: boolean }>({ sku: null, isNew: true });
  const [skuDeleteConfirm, setSkuDeleteConfirm] = useState<{ skuId: number; skuCode: string } | null>(null);
  const [discardSpuModal, setDiscardSpuModal] = useState(false);
  const [confirmModal, setConfirmModal] = useState<{ type: "publish" | "unpublish" | "delete"; loading: boolean } | null>(null);
  const { success: toastSuccess, error: toastError } = useToast();
  const [actionError, setActionError] = useState<{ message: string; errors?: string[] } | null>(null);
  const [expandedSkus, setExpandedSkus] = useState<Set<number>>(new Set());
  const [lightbox, setLightbox] = useState<{ images: { url: string }[]; index: number } | null>(null);
  const [skuStatusLoading, setSkuStatusLoading] = useState<number | null>(null);

  const toggleSkuExpand = (skuId: number) => {
    setExpandedSkus((prev) => { const next = new Set(prev); if (next.has(skuId)) next.delete(skuId); else next.add(skuId); return next; });
  };

  // SKU 状态切换确认弹窗
  const [skuStatusConfirm, setSkuStatusConfirm] = useState<{ skuId: number; skuCode: string; currentStatus: string; isLastActive: boolean } | null>(null);

  const requestSkuStatusToggle = useCallback((skuId: number, currentStatus: string, skuCode: string) => {
    if (!product) return;
    // 判断是否是最后一个在售 SKU（仅在停售时需要检测）
    const isLastActive = currentStatus === "ACTIVE" &&
      product.skus.filter((s) => s.status === "ACTIVE").length === 1;
    setSkuStatusConfirm({ skuId, skuCode, currentStatus, isLastActive });
  }, [product]);

  const executeSkuStatusToggle = useCallback(async () => {
    if (!product || !skuStatusConfirm) return;
    const { skuId, currentStatus } = skuStatusConfirm;
    const newStatus = currentStatus === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    setSkuStatusConfirm(null);
    setSkuStatusLoading(skuId);
    try {
      const res = await operatorProductsApi.updateSkuStatus(product.id, skuId, { status: newStatus as "ACTIVE" | "INACTIVE" });
      await mutate();
      if (res.product_auto_delisted) {
        toastSuccess(t("skuDeactivatedAndProductDelisted"));
      } else {
        toastSuccess(newStatus === "ACTIVE" ? t("skuActivated") : t("skuDeactivated"));
      }
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : t("actionError"));
    } finally {
      setSkuStatusLoading(null);
    }
  }, [product, skuStatusConfirm, mutate, toastSuccess, t]);

  // 进入编辑态
  const enterEditMode = useCallback(() => {
    if (!product) return;
    // 按当前 locale 选取编辑值:zh→_zh, en→_en, 其他→后端 get_localized 返回的字段
    const pick = (zh: string | null, en: string | null, fb?: string | null) => {
      if (locale === "zh") return zh || fb || en || "";
      if (locale === "en") return en || fb || zh || "";
      return fb || en || zh || "";
    };
    setSpuForm({
      name: pick(product.name_zh, product.name_en, product.name),
      description: pick(product.description_zh, product.description_en, product.description),
      brand: pick(product.brand_zh, product.brand_en, product.brand),
      origin: pick(product.origin_zh, product.origin_en, product.origin),
      hs_code: product.hs_code,
      certifications: product.certifications || [],
      selling_points: pick(product.selling_points_zh, product.selling_points_en, product.selling_points),
      is_featured: product.is_featured,
      attributes: product.attributes.filter((a) => a.sku_id == null).map((a) => ({ attr_key: a.attr_key, attr_value: a.attr_value })),
    });
    spuDirtyRef.current = false;
    setSaveError(null);
    setIsEditing(true);
    if (product.category_code) {
      operatorProductsApi.getAttrTemplates(product.category_code).then((templates) => {
        setSkuTemplates(templates.filter((t) => t.scope === "SKU"));
      }).catch(() => {});
    }
  }, [product, locale]);

  // 仅首次加载时根据 URL ?edit=true 进入编辑态（保存后不再重入）
  const editInitRef = useRef(false);
  useEffect(() => {
    if (startInEdit && product && hasPermission(Permissions.PRODUCT_WRITE) && !editInitRef.current) {
      editInitRef.current = true;
      enterEditMode();
    }
  }, [startInEdit, product, hasPermission, enterEditMode]);

  // i18n 字段取值:fallback 是后端 get_localized() 返回的已本地化值(含 sw 等)
  const localized = useCallback(
    (zhVal: string | null, enVal: string | null, fallback?: string | null) => {
      if (locale === "zh") return zhVal || fallback || enVal || "";
      if (locale === "en") return enVal || fallback || zhVal || "";
      // sw 等其他语言:优先用后端已本地化的 fallback
      return fallback || enVal || zhVal || "";
    }, [locale]
  );

  // 品类名解析
  const categoryName = useMemo(() => {
    if (!product || !categoryTree?.length) return product?.category_code || "";
    const code = product.category_code;
    const findNode = (nodes: typeof categoryTree, target: string): string | null => {
      for (const n of nodes) {
        if (n.code === target) return n.name;
        if (n.children) { const f = findNode(n.children, target); if (f) return f; }
      }
      return null;
    };
    const parts = code.split(".");
    if (parts.length === 3) {
      const l1Code = parts[0];
      const l2Code = `${parts[0]}.${parts[1]}`;
      const l1Name = findNode(categoryTree, l1Code);
      const l2Name = findNode(categoryTree, l2Code);
      const l3Name = findNode(categoryTree, code);
      const names = [l1Name, l2Name, l3Name].filter(Boolean);
      if (names.length) return names.join(" > ");
    }
    return findNode(categoryTree, code) || code;
  }, [product, categoryTree]);

  // 供应商汇总
  const supplierSummary = useMemo(() => {
    if (!product) return [];
    const map = new Map<number, { name: string; skuCodes: string[]; isPreferred: boolean; cifPrice: number | null; leadTime: number | null }>();
    for (const sku of product.skus) {
      for (const sr of sku.supplier_relations) {
        const existing = map.get(sr.supplier_org_id);
        if (existing) { existing.skuCodes.push(sku.sku_code); if (sr.is_preferred) existing.isPreferred = true; }
        else map.set(sr.supplier_org_id, { name: sr.supplier_org_name, skuCodes: [sku.sku_code], isPreferred: sr.is_preferred, cifPrice: sr.cif_price_usd ? Number(sr.cif_price_usd) : null, leadTime: sr.supplier_lead_time_days });
      }
    }
    return Array.from(map.values());
  }, [product]);

  // 概览
  const overview = useMemo(() => {
    if (!product) return null;
    const activeSkus = product.skus.filter((s) => s.status === "ACTIVE");
    const allMoqs = activeSkus.map((s) => s.moq).filter(Boolean);
    return { skuTotal: product.skus.length, skuActive: activeSkus.length, minMoq: allMoqs.length > 0 ? Math.min(...allMoqs) : null };
  }, [product]);

  // 退出编辑态
  const exitEditMode = useCallback(() => {
    setIsEditing(false);
    spuDirtyRef.current = false;
    if (searchParams.get("edit")) {
      router.replace(`/${locale}/operator/products/${productId}`, { scroll: false });
    }
  }, [searchParams, router, locale, productId]);

  const cancelEdit = () => {
    if (spuDirtyRef.current) setDiscardSpuModal(true);
    else exitEditMode();
  };

  // SPU 表单变更跟踪
  const updateSpuForm = useCallback((value: ProductUpdateInput) => {
    setSpuForm(value);
    spuDirtyRef.current = true;
  }, []);

  // ── SPU 基础信息保存 ──
  const handleSpuSave = async () => {
    if (!product) return;
    if (!spuForm.name?.trim()) {
      setSaveError(t("validationNameRequired"));
      return;
    }
    setSpuSaving(true);
    setSaveError(null);
    try {
      await operatorProductsApi.update(product.id, spuForm);
      await mutate();
      spuDirtyRef.current = false;
      exitEditMode();
      toastSuccess(t("spuSaved"));
    } catch (err: unknown) {
      setSaveError(translateError(err));
    } finally {
      setSpuSaving(false);
    }
  };

  // ── 图片即时操作 ──
  const handleImageUpload = async (files: FileList) => {
    if (!product) return;
    setImageUploading(true);
    try {
      for (const file of Array.from(files)) {
        await operatorProductsApi.uploadImage(product.id, file);
      }
      await mutate();
      toastSuccess(t("imageUploaded"));
    } catch (err: unknown) {
      toastError(translateError(err));
    } finally {
      setImageUploading(false);
    }
  };

  const handleImageDelete = async (imageId: number) => {
    if (!product) return;
    try {
      await operatorProductsApi.deleteImage(product.id, imageId);
      await mutate();
      toastSuccess(t("imageDeleted"));
    } catch (err: unknown) {
      toastError(translateError(err));
    }
  };

  const handleSetMainImage = async (imageId: number) => {
    if (!product) return;
    try {
      await operatorProductsApi.setMainImage(product.id, imageId);
      await mutate();
      toastSuccess(t("mainImageSet"));
    } catch (err: unknown) {
      toastError(translateError(err));
    }
  };

  // 状态操作
  const handleStatusAction = async () => {
    if (!confirmModal || !product) return;
    setConfirmModal({ ...confirmModal, loading: true }); setActionError(null);
    try {
      if (confirmModal.type === "delete") {
        await operatorProductsApi.remove(product.id);
        toastSuccess(tList("toastDeleted"));
        setTimeout(() => router.push(`/${locale}/operator/products`), 500);
      } else {
        const newStatus = confirmModal.type === "publish" ? "ACTIVE" : "INACTIVE";
        await operatorProductsApi.updateStatus(product.id, { status: newStatus });
        toastSuccess(confirmModal.type === "publish" ? tList("toastPublished") : tList("toastUnpublished"));
        await mutate();
      }
      setConfirmModal(null);
    } catch (err: unknown) {
      // 解析上架校验的结构化错误列表 [{key, params}]，翻译后展示
      if (err instanceof ApiError && err.messageParams && Array.isArray(err.messageParams.errors)) {
        const rawErrors = err.messageParams.errors as Array<{ key: string; params?: Record<string, string> } | string>;
        const translated = rawErrors.map((e) => {
          if (typeof e === "object" && e.key) {
            try { return tList(e.key, e.params ?? {}); } catch { return e.key; }
          }
          return String(e);
        });
        setActionError({ message: translateError(err), errors: translated });
      } else {
        setActionError({ message: translateError(err) });
      }
      setConfirmModal({ ...confirmModal, loading: false });
    }
  };

  // ── SKU 增量操作（确认即落库）──
  const openSkuModal = (sku: SkuOperatorDetail | null, isNew: boolean) => { setSkuModalData({ sku, isNew }); setSkuModalOpen(true); };

  const handleSkuModalConfirm = async (data: SkuFormData) => {
    if (!product) return;
    setSkuSaving(true);
    setSaveError(null);
    try {
      if (skuModalData.isNew) {
        const result = await operatorProductsApi.createSku(product.id, {
          manufacturer_model: data.manufacturer_model,
          name: data.name,
          color: data.color,
          material: data.material,
          source_lang: locale,
          price_min: data.price_min,
          price_max: data.price_max,
          moq: data.moq,
          lead_time_min: data.lead_time_min,
          lead_time_max: data.lead_time_max,
          packing_quantity: data.packing_quantity,
          gross_weight_kg: data.gross_weight_kg,
          volume_cbm: data.volume_cbm,
          can_consolidate: data.can_consolidate,
          cargo_type: data.cargo_type,
          is_default: data.is_default,
          price_tiers: data.price_tiers.length > 0 ? data.price_tiers : undefined,
          attributes: data.attributes.length > 0 ? data.attributes : undefined,
        });
        // 新建 SKU 的图片上传
        for (const file of data.imageFiles) {
          await operatorProductsApi.uploadImage(product.id, file, result.id);
        }
      } else if (skuModalData.sku) {
        const skuId = skuModalData.sku.id;
        await operatorProductsApi.updateSku(product.id, skuId, {
          manufacturer_model: data.manufacturer_model,
          name: data.name,
          color: data.color,
          material: data.material,
          price_min: data.price_min,
          price_max: data.price_max,
          moq: data.moq,
          lead_time_min: data.lead_time_min,
          lead_time_max: data.lead_time_max,
          packing_quantity: data.packing_quantity,
          gross_weight_kg: data.gross_weight_kg,
          volume_cbm: data.volume_cbm,
          can_consolidate: data.can_consolidate,
          cargo_type: data.cargo_type,
          is_default: data.is_default,
          price_tiers: data.price_tiers.length > 0 ? data.price_tiers : undefined,
          attributes: data.attributes.length > 0 ? data.attributes : undefined,
        });
        // 编辑 SKU 的图片变更
        for (const imgId of data.removedImageIds) {
          await operatorProductsApi.deleteImage(product.id, imgId);
        }
        for (const file of data.imageFiles) {
          await operatorProductsApi.uploadImage(product.id, file, skuId);
        }
      }
      await mutate();
      setSkuModalOpen(false);
      toastSuccess(t("skuSaved"));
    } catch (err: unknown) {
      toastError(translateError(err));
    } finally {
      setSkuSaving(false);
    }
  };

  const requestSkuDelete = (skuId: number, skuCode: string) => {
    setSkuDeleteConfirm({ skuId, skuCode });
  };

  const executeSkuDelete = async () => {
    if (!product || !skuDeleteConfirm) return;
    const { skuId } = skuDeleteConfirm;
    setSkuDeleteConfirm(null);
    setSaveError(null);
    try {
      await operatorProductsApi.deleteSku(product.id, skuId);
      await mutate();
      toastSuccess(t("skuDeleted"));
    } catch (err: unknown) {
      setSaveError(translateError(err));
    }
  };

  // Loading / Error / 404
  if (isLoading) return <DetailSkeleton />;
  if (error || !product) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Package className="h-12 w-12 text-slate-300" />
        <p className="text-slate-600 text-sm">{t("notFound")}</p>
        <button onClick={() => router.push(`/${locale}/operator/products`)} className="text-sm text-blue-600 hover:underline">{t("backToList")}</button>
      </div>
    );
  }

  const status = STATUS_STYLES[product.status] || STATUS_STYLES.DRAFT;
  const canWrite = hasPermission(Permissions.PRODUCT_WRITE);
  const canApprove = hasPermission(Permissions.PRODUCT_APPROVE);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className={`sticky top-0 z-10 border-b px-6 py-4 transition-colors ${isEditing ? "bg-blue-50 border-blue-200" : "bg-white border-slate-200"}`}>
        <div className="flex items-center justify-between max-w-[1400px] mx-auto">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push(`/${locale}/operator/products`)} className="text-slate-500 hover:text-slate-700 flex items-center gap-1 text-sm">
              <ArrowLeft className="h-4 w-4" />{t("backToList")}
            </button>
            <span className="text-slate-300">|</span>
            <h1 className="text-lg font-semibold text-slate-900 truncate max-w-[400px]">
              {localized(product.name_zh, product.name_en, product.name)}
            </h1>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${status.bg} ${status.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
              {t(status.labelKey)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <button onClick={cancelEdit} disabled={spuSaving} className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">{t("cancelEdit")}</button>
                <button onClick={handleSpuSave} disabled={spuSaving} className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60">
                  {spuSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{t("save")}
                </button>
                {canApprove && (product.status === "DRAFT" || product.status === "INACTIVE") && <button onClick={() => setConfirmModal({ type: "publish", loading: false })} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"><TrendingUp className="h-3.5 w-3.5" />{tList("publish")}</button>}
              </>
            ) : (
              <>
                {canWrite && (product.status === "DRAFT" || product.status === "INACTIVE") && <button onClick={enterEditMode} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"><Edit3 className="h-3.5 w-3.5" />{t("edit")}</button>}
                {canApprove && (product.status === "DRAFT" || product.status === "INACTIVE") && <button onClick={() => setConfirmModal({ type: "publish", loading: false })} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"><TrendingUp className="h-3.5 w-3.5" />{tList("publish")}</button>}
                {canApprove && product.status === "ACTIVE" && <button onClick={() => setConfirmModal({ type: "unpublish", loading: false })} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"><TrendingDown className="h-3.5 w-3.5" />{tList("unpublish")}</button>}
                {canWrite && (product.status === "DRAFT" || product.status === "INACTIVE") && <button onClick={() => setConfirmModal({ type: "delete", loading: false })} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"><Trash2 className="h-3.5 w-3.5" />{tList("delete")}</button>}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-[1400px] mx-auto px-6 py-6 flex flex-col lg:flex-row gap-6">
        {/* Left Column */}
        <div className="flex-1 flex flex-col gap-5 min-w-0">
          {saveError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" /><div className="flex-1">{saveError}</div>
              <button onClick={() => setSaveError(null)}><X className="h-4 w-4 text-red-400" /></button>
            </div>
          )}

          {/* 基本信息 */}
          {isEditing ? (
            <EditBasicInfo product={product} value={spuForm} onChange={updateSpuForm} />
          ) : (
            <section className="bg-white rounded-lg shadow-sm p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4">{t("basicInfo")}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
                <FieldDisplay label={t("spuCode")} value={product.spu_code} mono />
                <FieldDisplay label={t("category")} value={categoryName} />
                <FieldDisplay label={t("brand")} value={localized(product.brand_zh, product.brand_en, product.brand)} />
                <FieldDisplay label={t("origin")} value={localized(product.origin_zh, product.origin_en, product.origin)} />
                <FieldDisplay label={t("hsCode")} value={product.hs_code} />
                <div>
                  <span className="text-slate-400 text-xs">{t("certifications")}</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {product.certifications?.length ? product.certifications.map((c, i) => (
                      <span key={i} className="inline-block bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded text-xs font-medium">{String(c)}</span>
                    )) : <span className="text-slate-400 text-xs">—</span>}
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <span className="text-slate-400 text-xs">{t("sellingPoints")}</span>
                  <p className="mt-1 text-slate-700 text-sm">{localized(product.selling_points_zh, product.selling_points_en, product.selling_points) || "—"}</p>
                </div>
                <div className="sm:col-span-2">
                  <span className="text-slate-400 text-xs">{t("description")}</span>
                  <p className="mt-1 text-slate-600 text-sm leading-relaxed line-clamp-4">{localized(product.description_zh, product.description_en, product.description) || "—"}</p>
                </div>
              </div>
            </section>
          )}

          {/* SKU 变体表格 */}
          <section id="sku-section" className="bg-white rounded-lg shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800">
                {t("skuVariants")} <span className="text-slate-400 font-normal">({product.skus.length})</span>
              </h3>
              {isEditing && (
                <button type="button" onClick={() => openSkuModal(null, true)} disabled={skuSaving} className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium disabled:opacity-60">
                  {skuSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />} {t("addSku")}
                </button>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-[700px] w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="px-3 py-2.5 text-left text-slate-500 font-medium whitespace-nowrap">{t("skuCode")}</th>
                    <th className="px-3 py-2.5 text-left text-slate-500 font-medium whitespace-nowrap">{t("specs")}</th>
                    <th className="px-3 py-2.5 text-right text-slate-500 font-medium whitespace-nowrap">{t("priceRange")}</th>
                    <th className="px-3 py-2.5 text-right text-slate-500 font-medium whitespace-nowrap">MOQ</th>
                    <th className="px-3 py-2.5 text-center text-slate-500 font-medium whitespace-nowrap">{t("status")}</th>
                    <th className="px-3 py-2.5 text-center text-slate-500 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {product.skus.map((sku) => (
                    <SkuRow key={sku.id} sku={sku} locale={locale} localized={localized} expanded={expandedSkus.has(sku.id)} onToggle={() => toggleSkuExpand(sku.id)} t={t} isEditing={isEditing} onEdit={() => openSkuModal(sku, false)} onDelete={() => requestSkuDelete(sku.id, sku.sku_code)} onStatusToggle={canWrite ? () => requestSkuStatusToggle(sku.id, sku.status, sku.sku_code) : undefined} statusLoading={skuStatusLoading === sku.id} onImageClick={(images, index) => setLightbox({ images, index })} unit={product.unit} currency={product.currency} />
                  ))}
                </tbody>
              </table>
              {product.skus.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-slate-400 text-sm">{t("noSkus")}</p>
                </div>
              )}
            </div>
          </section>

          {/* 商品图片（仅 SPU 级，sku_id 为空） */}
          {(() => { const spuImages = product.images.filter((img) => img.sku_id == null); return (
          <section id="image-section" className="bg-white rounded-lg shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800">{t("productImages")} <span className="text-slate-400 font-normal">({spuImages.length}/8)</span></h3>
              {isEditing && spuImages.length < 8 && (
                <label className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 cursor-pointer">
                  {imageUploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                  {t("uploadImage")}
                  <input type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={(e) => { if (e.target.files) handleImageUpload(e.target.files); e.target.value = ""; }} disabled={imageUploading} />
                </label>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              {spuImages.map((img, idx) => (
                <div
                  key={img.id}
                  className={`relative group w-24 h-24 rounded-lg overflow-hidden border-2 cursor-pointer hover:shadow-md transition-shadow ${img.image_type === "MAIN" ? "border-blue-500" : "border-slate-200"} bg-slate-100`}
                  onClick={() => !isEditing && setLightbox({ images: spuImages.map((i) => ({ url: i.full_url })), index: idx })}
                >
                  <img src={img.full_url} alt="" className="w-full h-full object-cover" loading="lazy" />
                  {img.image_type === "MAIN" && <span className="absolute top-0 left-0 bg-blue-500 text-white text-[10px] px-1.5 py-0.5 rounded-br">{t("mainImage")}</span>}
                  {isEditing && (
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100">
                      {img.image_type !== "MAIN" && (
                        <button onClick={(e) => { e.stopPropagation(); handleSetMainImage(img.id); }} className="p-1 bg-white/90 rounded-full hover:bg-white" title={t("setAsMain")}>
                          <Star className="h-3.5 w-3.5 text-amber-500" />
                        </button>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); handleImageDelete(img.id); }} className="p-1 bg-white/90 rounded-full hover:bg-white" title={t("deleteImage")}>
                        <X className="h-3.5 w-3.5 text-red-500" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {spuImages.length === 0 && <div className="text-slate-400 text-sm">{t("noImages")}</div>}
            </div>
          </section>
          ); })()}

          {/* SPU 属性 */}
          {product.attributes.filter((a) => a.sku_id == null).length > 0 && (
            <section className="bg-white rounded-lg shadow-sm p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4">{t("spuAttributes")}</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {product.attributes.filter((a) => a.sku_id == null).sort((a, b) => a.sort_order - b.sort_order).map((attr) => (
                  <div key={attr.attr_key} className="bg-slate-50 rounded-lg px-3 py-2">
                    <span className="text-slate-400 text-[11px]">{attr.display_name || attr.attr_key}</span>
                    <div className="text-slate-800 text-sm mt-0.5">{attr.attr_value}{attr.attr_unit ? ` ${attr.attr_unit}` : ""}</div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right Sidebar — sticky 跟随滚动 */}
        <div className="w-full lg:w-72 flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
          <div className="bg-white rounded-lg shadow-sm p-4">
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("productStatus")}</h4>
            <div className="flex items-center gap-2 mb-3">
              <span className={`w-2.5 h-2.5 rounded-full ${status.dot}`} />
              <span className={`text-sm font-medium ${status.text}`}>{t(status.labelKey)}</span>
            </div>
            <div className="text-xs text-slate-500 space-y-1.5">
              <div>{t("createdAt")}：{formatTime(product.created_at)}</div>
              <div>{t("updatedAt")}：{formatTime(product.updated_at)}</div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("overview")}</h4>
            <div className="text-xs space-y-2">
              <div className="flex justify-between"><span className="text-slate-400">{t("skuCount")}</span><span className="text-slate-700 font-medium">{overview?.skuTotal} {t("unit")} ({overview?.skuActive} {t("active")})</span></div>
              <div className="flex justify-between"><span className="text-slate-400">{t("priceRange")}</span><span className="text-slate-700 font-medium">{formatPrice(product.skus.reduce((min, s) => s.price_min != null ? Math.min(min, Number(s.price_min)) : min, Infinity) === Infinity ? null : product.skus.reduce((min, s) => s.price_min != null ? Math.min(min, Number(s.price_min)) : min, Infinity), product.skus.reduce((max, s) => s.price_max != null ? Math.max(max, Number(s.price_max)) : max, -Infinity) === -Infinity ? null : product.skus.reduce((max, s) => s.price_max != null ? Math.max(max, Number(s.price_max)) : max, -Infinity), product.currency || "TZS")}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">{t("minMoq")}</span><span className="text-slate-700 font-medium">{overview?.minMoq != null ? `${overview.minMoq} pcs` : "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">{t("featured")}</span><span className="text-slate-700 font-medium">{product.is_featured ? "⭐ " + t("yes") : t("no")}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">{t("createdBy")}</span><span className="text-slate-700 font-medium">{product.created_by_name || "—"}</span></div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <h4 className="text-xs font-semibold text-slate-700 mb-3">{t("supplierRelations")} <span className="text-slate-400 font-normal">({supplierSummary.length})</span></h4>
            {supplierSummary.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {supplierSummary.map((s, i) => (
                  <div key={i} className={`text-xs ${i > 0 ? "pt-2.5" : ""} pb-2.5`}>
                    <div className="font-medium text-slate-800">{s.name}</div>
                    <div className="text-slate-500 mt-0.5">{t("coversSku")}: {s.skuCodes.join(", ")}{s.isPreferred && <span className="ml-1">⭐</span>}</div>
                    <div className="text-slate-500">{s.cifPrice != null && `CIF: $${s.cifPrice}/pcs`}{s.cifPrice != null && s.leadTime != null && " · "}{s.leadTime != null && `${t("leadTime")}: ${s.leadTime}d`}</div>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-slate-400">{t("noSuppliers")}</p>}
          </div>
        </div>
      </div>

      {/* 确认弹窗 */}
      {confirmModal && actionError ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md bg-white rounded-xl p-6 shadow-2xl mx-4">
            <h3 className="text-base font-semibold text-slate-900 mb-2">{t("publishFailedTitle")}</h3>
            <p className="text-sm text-slate-600 mb-3">{t("publishFailedHint")}</p>
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              <ul className="space-y-1.5">
                {(actionError.errors || [actionError.message]).map((e, i) => {
                  const isSkuErr = e.startsWith("SKU ") || e.toLowerCase().includes("sku");
                  const isImgErr = e.toLowerCase().includes("image");
                  const isAttrErr = e.toLowerCase().includes("attribute");
                  const icon = isSkuErr ? "📦" : isImgErr ? "🖼️" : isAttrErr ? "📋" : "⚠️";
                  return <li key={i} className="flex items-start gap-1.5"><span>{icon}</span><span>{e}</span></li>;
                })}
              </ul>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => { setConfirmModal(null); setActionError(null); }} className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">{tList("cancel")}</button>
              <button onClick={() => {
                const errors = actionError?.errors || [];
                const hasSkuErr = errors.some((e) => e.toLowerCase().includes("sku") || e.toLowerCase().includes("price"));
                const hasImgErr = errors.some((e) => e.toLowerCase().includes("image"));
                setConfirmModal(null); setActionError(null); enterEditMode();
                setTimeout(() => {
                  const target = hasSkuErr ? "sku-section" : hasImgErr ? "image-section" : null;
                  if (target) document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "center" });
                }, 100);
              }} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">{t("goEdit")}</button>
            </div>
          </div>
        </div>
      ) : (
        <ConfirmModal
          open={!!confirmModal}
          title={
            confirmModal?.type === "publish" ? tList("confirmPublishTitle")
            : confirmModal?.type === "unpublish" ? tList("confirmUnpublishTitle")
            : confirmModal?.type === "delete" ? tList("confirmDeleteTitle")
            : ""
          }
          description={
            confirmModal?.type === "publish" ? tList("confirmPublishMsg", { name: product.name })
            : confirmModal?.type === "unpublish" ? tList("confirmUnpublishMsg", { name: product.name })
            : confirmModal?.type === "delete" ? tList("confirmDeleteMsg", { name: product.name })
            : ""
          }
          confirmLabel={
            confirmModal?.type === "publish" ? tList("confirmPublishBtn")
            : confirmModal?.type === "unpublish" ? tList("confirmUnpublishBtn")
            : confirmModal?.type === "delete" ? tList("confirmDeleteBtn")
            : ""
          }
          cancelLabel={tList("cancel")}
          variant={confirmModal?.type === "delete" ? "danger" : confirmModal?.type === "unpublish" ? "warning" : "primary"}
          loading={confirmModal?.loading}
          onConfirm={handleStatusAction}
          onCancel={() => { setConfirmModal(null); setActionError(null); }}
        />
      )}

      {/* SPU 未保存变更确认 */}
      <ConfirmModal
        open={discardSpuModal}
        title={t("confirmDiscardTitle")}
        description={t("unsavedSpuChanges")}
        confirmLabel={t("discardAndExit")}
        cancelLabel={tList("cancel")}
        variant="warning"
        onConfirm={() => { setDiscardSpuModal(false); exitEditMode(); }}
        onCancel={() => setDiscardSpuModal(false)}
      />

      {/* SKU 删除确认 */}
      <ConfirmModal
        open={!!skuDeleteConfirm}
        title={t("confirmDeleteSkuTitle")}
        description={t("confirmDeleteSkuMsg", { code: skuDeleteConfirm?.skuCode ?? "" })}
        confirmLabel={t("deleteSku")}
        cancelLabel={tList("cancel")}
        variant="danger"
        onConfirm={executeSkuDelete}
        onCancel={() => setSkuDeleteConfirm(null)}
      />

      {/* SKU 状态切换确认 */}
      <ConfirmModal
        open={!!skuStatusConfirm}
        title={skuStatusConfirm?.currentStatus === "ACTIVE" ? t("skuDeactivateTitle") : t("skuActivateTitle")}
        description={
          skuStatusConfirm?.isLastActive && product?.status === "ACTIVE"
            ? t("skuLastActiveWarning", { code: skuStatusConfirm.skuCode })
            : skuStatusConfirm?.currentStatus === "ACTIVE"
              ? t("skuDeactivateMsg", { code: skuStatusConfirm?.skuCode ?? "" })
              : t("skuActivateMsg", { code: skuStatusConfirm?.skuCode ?? "" })
        }
        confirmLabel={skuStatusConfirm?.currentStatus === "ACTIVE" ? t("skuDeactivateBtn") : t("skuActivateBtn")}
        cancelLabel={tList("cancel")}
        variant={skuStatusConfirm?.isLastActive && product?.status === "ACTIVE" ? "danger" : "warning"}
        onConfirm={executeSkuStatusToggle}
        onCancel={() => setSkuStatusConfirm(null)}
      />

      {/* SKU Modal */}
      <SkuEditModal
        open={skuModalOpen} onClose={() => setSkuModalOpen(false)} onConfirm={handleSkuModalConfirm} isNew={skuModalData.isNew} skuTemplates={skuTemplates} currency={product.currency}
        initial={skuModalData.sku ? { sku_code: skuModalData.sku.sku_code, manufacturer_model: skuModalData.sku.manufacturer_model, name: localized(skuModalData.sku.name_zh, skuModalData.sku.name_en, skuModalData.sku.name), color: localized(skuModalData.sku.color_zh, skuModalData.sku.color_en, skuModalData.sku.color), material: localized(skuModalData.sku.material_zh, skuModalData.sku.material_en, skuModalData.sku.material), price_min: skuModalData.sku.price_min ? Number(skuModalData.sku.price_min) : null, price_max: skuModalData.sku.price_max ? Number(skuModalData.sku.price_max) : null, moq: skuModalData.sku.moq, lead_time_min: skuModalData.sku.lead_time_min, lead_time_max: skuModalData.sku.lead_time_max, packing_quantity: skuModalData.sku.packing_quantity, gross_weight_kg: skuModalData.sku.gross_weight_kg ? Number(skuModalData.sku.gross_weight_kg) : null, volume_cbm: skuModalData.sku.volume_cbm ? Number(skuModalData.sku.volume_cbm) : null, can_consolidate: skuModalData.sku.can_consolidate, cargo_type: skuModalData.sku.cargo_type, is_default: skuModalData.sku.is_default, status: skuModalData.sku.status, price_tiers: skuModalData.sku.price_tiers.map((pt) => ({ min_qty: pt.min_qty, max_qty: pt.max_qty, unit_price: Number(pt.unit_price), currency: pt.currency })), attributes: skuModalData.sku.attributes.map((a) => ({ attr_key: a.attr_key, attr_value: a.attr_value })), imageFiles: [], existingImages: skuModalData.sku.images.map((img) => ({ id: img.id, url: img.full_url })), removedImageIds: [] } : null}
      />

      {/* Lightbox 图片预览 */}
      {lightbox && (
        <div className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center" onClick={() => setLightbox(null)}>
          <button onClick={(e) => { e.stopPropagation(); setLightbox(null); }} className="absolute top-4 right-4 text-white/80 hover:text-white z-10"><X className="h-8 w-8" /></button>
          {lightbox.images.length > 1 && (
            <>
              <button onClick={(e) => { e.stopPropagation(); setLightbox({ ...lightbox, index: (lightbox.index - 1 + lightbox.images.length) % lightbox.images.length }); }} className="absolute left-4 text-white/80 hover:text-white z-10"><ChevronLeft className="h-10 w-10" /></button>
              <button onClick={(e) => { e.stopPropagation(); setLightbox({ ...lightbox, index: (lightbox.index + 1) % lightbox.images.length }); }} className="absolute right-4 text-white/80 hover:text-white z-10"><ChevronRight className="h-10 w-10" /></button>
            </>
          )}
          <img
            src={lightbox.images[lightbox.index].url}
            alt=""
            className="max-w-[90vw] max-h-[85vh] object-contain rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
          <div className="absolute bottom-4 text-white/60 text-sm">{lightbox.index + 1} / {lightbox.images.length}</div>
        </div>
      )}

    </div>
  );
}

// 子组件
function FieldDisplay({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (<div><span className="text-slate-400 text-xs">{label}</span><div className={`mt-0.5 text-slate-800 text-sm ${mono ? "font-mono" : ""}`}>{value || "—"}</div></div>);
}

function SkuRow({ sku, locale, localized, expanded, onToggle, t, isEditing, onEdit, onDelete, onStatusToggle, statusLoading, onImageClick, unit, currency }: {
  sku: SkuOperatorDetail; locale: string; localized: (zh: string | null, en: string | null, fallback?: string | null) => string;
  expanded: boolean; onToggle: () => void; t: ReturnType<typeof useTranslations>; isEditing?: boolean; onEdit?: () => void; onDelete?: () => void;
  onStatusToggle?: () => void; statusLoading?: boolean; onImageClick?: (images: { url: string }[], index: number) => void;
  unit: string; currency: string;
}) {
  const skuStatus = sku.status === "ACTIVE" ? { bg: "bg-emerald-50", text: "text-emerald-700", label: t("skuStatusActive") } : { bg: "bg-slate-100", text: "text-slate-600", label: t("skuStatusInactive") };
  const specs = [localized(sku.color_zh, sku.color_en, sku.color), localized(sku.material_zh, sku.material_en, sku.material), unit].filter(Boolean).join(" / ");
  return (
    <>
      <tr className={`border-b ${expanded ? "border-slate-100" : "border-slate-200"} hover:bg-slate-50/50 ${!isEditing ? "cursor-pointer" : ""}`} onClick={!isEditing ? onToggle : undefined}>
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-slate-700">{sku.sku_code}</span>
            {sku.is_default && <span className="bg-blue-500 text-white text-[9px] px-1.5 py-0.5 rounded font-medium">{t("default")}</span>}
          </div>
          {(localized(sku.name_zh, sku.name_en, sku.name) || sku.manufacturer_model) && (
            <div className="text-slate-400 text-[11px] mt-0.5">
              {localized(sku.name_zh, sku.name_en, sku.name)}{localized(sku.name_zh, sku.name_en, sku.name) && sku.manufacturer_model ? " · " : ""}{sku.manufacturer_model || ""}
            </div>
          )}
        </td>
        <td className="px-3 py-2.5 text-slate-600">{specs || "—"}</td>
        <td className="px-3 py-2.5 text-right text-slate-800 font-medium">{formatPrice(sku.price_min ? Number(sku.price_min) : null, sku.price_max ? Number(sku.price_max) : null, currency)}</td>
        <td className="px-3 py-2.5 text-right text-slate-600">{sku.moq} {unit?.toLowerCase()}</td>
        <td className="px-3 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
          {onStatusToggle && !isEditing ? (
            <Toggle
              checked={sku.status === "ACTIVE"}
              onChange={onStatusToggle}
              label={skuStatus.label}
              loading={statusLoading}
              title={sku.status === "ACTIVE" ? t("skuDeactivate") : t("skuActivate")}
            />
          ) : (
            <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${skuStatus.bg} ${skuStatus.text}`}>{skuStatus.label}</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-center" onClick={isEditing ? (e) => e.stopPropagation() : undefined}>
          {isEditing ? (
            <div className="flex items-center justify-center gap-2">
              <button onClick={onEdit} className="text-blue-600 hover:text-blue-700 text-[11px] font-medium">{t("edit")}</button>
              <button onClick={onDelete} className="text-red-500 hover:text-red-700 text-[11px] font-medium">{t("deleteSku")}</button>
            </div>
          ) : <span className="text-slate-400">{expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</span>}
        </td>
      </tr>
      {expanded && !isEditing && (
        <tr className="bg-slate-50/80 border-b-2 border-slate-200"><td colSpan={6} className="px-6 py-4"><SkuExpandedDetails sku={sku} locale={locale} t={t} onImageClick={onImageClick} unit={unit} currency={currency} /></td></tr>
      )}
    </>
  );
}

function SkuExpandedDetails({ sku, locale, t, onImageClick, unit, currency }: { sku: SkuOperatorDetail; locale: string; t: ReturnType<typeof useTranslations>; onImageClick?: (images: { url: string }[], index: number) => void; unit: string; currency: string }) {
  const loc = (zh: string | null, en: string | null, fb?: string | null) => {
    if (locale === "zh") return zh || fb || en || "";
    if (locale === "en") return en || fb || zh || "";
    return fb || en || zh || "";
  };
  const Val = ({ v }: { v: string | number | null | undefined }) => <span className="text-slate-800">{v != null && v !== "" ? String(v) : "—"}</span>;

  return (
    <div className="space-y-5 text-xs">
      {/* 第一行：SKU 基础信息网格 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-x-6 gap-y-2">
        <div><span className="text-slate-400">SKU</span><div className="font-mono text-slate-800 mt-0.5">{sku.sku_code}</div></div>
        <div><span className="text-slate-400">{t("model")}</span><div className="mt-0.5"><Val v={sku.manufacturer_model} /></div></div>
        <div><span className="text-slate-400">{t("name")}</span><div className="mt-0.5"><Val v={loc(sku.name_zh, sku.name_en, sku.name)} /></div></div>
        <div><span className="text-slate-400">{t("color")}</span><div className="mt-0.5"><Val v={loc(sku.color_zh, sku.color_en, sku.color)} /></div></div>
        <div><span className="text-slate-400">{t("material")}</span><div className="mt-0.5"><Val v={loc(sku.material_zh, sku.material_en, sku.material)} /></div></div>
        <div><span className="text-slate-400">{t("currency")}</span><div className="mt-0.5"><Val v={currency} /></div></div>
      </div>

      <div className="border-t border-slate-100" />

      {/* 第二行：商务 + 物流 + 属性，分卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">

        {/* 阶梯价 */}
        <div className="bg-white border border-slate-100 rounded-lg p-3">
          <h5 className="font-semibold text-slate-700 mb-2">{t("priceTiers")}</h5>
          {sku.price_tiers.length > 0 ? (
            <table className="w-full">
              <thead><tr className="text-slate-400 border-b border-slate-100"><th className="text-left pb-1.5 font-medium">{t("tierQty")}</th><th className="text-right pb-1.5 font-medium">{t("tierPrice")}</th></tr></thead>
              <tbody>{sku.price_tiers.map((tier, i) => (
                <tr key={i} className="border-b border-slate-50 last:border-0">
                  <td className="py-1.5 text-slate-600">{tier.min_qty}{tier.max_qty ? ` - ${tier.max_qty}` : "+"} {unit?.toLowerCase()}</td>
                  <td className="py-1.5 text-right font-medium text-slate-800">{tier.currency} {Number(tier.unit_price).toLocaleString()}</td>
                </tr>
              ))}</tbody>
            </table>
          ) : <p className="text-slate-400">{t("noPriceTiers")}</p>}
        </div>

        {/* 物流参数 */}
        <div className="bg-white border border-slate-100 rounded-lg p-3">
          <h5 className="font-semibold text-slate-700 mb-2">{t("logistics")}</h5>
          <div className="space-y-1.5">
            <div className="flex justify-between"><span className="text-slate-400">{t("leadTime")}</span><Val v={sku.lead_time_min != null ? `${sku.lead_time_min}${sku.lead_time_max ? `-${sku.lead_time_max}` : ""} ${t("days")}` : null} /></div>
            <div className="flex justify-between"><span className="text-slate-400">{t("packingQty")}</span><Val v={sku.packing_quantity} /></div>
            <div className="flex justify-between"><span className="text-slate-400">{t("grossWeight")}</span><Val v={sku.gross_weight_kg != null ? `${Number(sku.gross_weight_kg)} kg` : null} /></div>
            <div className="flex justify-between"><span className="text-slate-400">{t("volume")}</span><Val v={sku.volume_cbm != null ? `${Number(sku.volume_cbm)} cbm` : null} /></div>
            <div className="flex justify-between"><span className="text-slate-400">{t("canConsolidate")}</span><span>{sku.can_consolidate ? "✅" : "❌"}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">{t("cargoType")}</span><Val v={sku.cargo_type} /></div>
          </div>
        </div>

        {/* SKU 属性 */}
        <div className="bg-white border border-slate-100 rounded-lg p-3">
          <h5 className="font-semibold text-slate-700 mb-2">{t("skuAttributes")}</h5>
          {sku.attributes.length > 0 ? (
            <div className="space-y-1.5">
              {sku.attributes.map((attr) => (
                <div key={attr.attr_key} className="flex justify-between">
                  <span className="text-slate-400">{attr.display_name || attr.attr_key}</span>
                  <span className="text-slate-800">{attr.attr_value}{attr.attr_unit ? ` ${attr.attr_unit}` : ""}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-slate-400">{t("noAttributes")}</p>}
        </div>
      </div>

      {/* SKU 图片 + 供应商 */}
      {(sku.images.length > 0 || sku.supplier_relations.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sku.images.length > 0 && (
            <div className="bg-white border border-slate-100 rounded-lg p-3">
              <h5 className="font-semibold text-slate-700 mb-2">{t("skuImages")} ({sku.images.length})</h5>
              <div className="flex flex-wrap gap-2">
                {sku.images.map((img, idx) => (
                  <div
                    key={img.id}
                    className="w-16 h-16 rounded border border-slate-200 overflow-hidden bg-slate-50 cursor-pointer hover:ring-2 hover:ring-blue-300 transition-shadow"
                    onClick={() => onImageClick?.(sku.images.map((i) => ({ url: i.full_url })), idx)}
                  >
                    <img src={img.full_url} alt="" className="w-full h-full object-cover" loading="lazy" />
                  </div>
                ))}
              </div>
            </div>
          )}
          {sku.supplier_relations.length > 0 && (
            <div className="bg-white border border-slate-100 rounded-lg p-3">
              <h5 className="font-semibold text-slate-700 mb-2">{t("suppliers")} ({sku.supplier_relations.length})</h5>
              <div className="space-y-2">
                {sku.supplier_relations.map((sr) => (
                  <div key={sr.id} className="flex items-start justify-between">
                    <div>
                      <span className="text-slate-800 font-medium">{sr.supplier_org_name}</span>
                      {sr.is_preferred && <span className="ml-1">⭐</span>}
                      <div className="text-slate-500 mt-0.5">{sr.supplier_currency} {Number(sr.supplier_price).toLocaleString()}{sr.cif_price_usd ? ` · CIF $${Number(sr.cif_price_usd)}` : ""}</div>
                    </div>
                    {sr.supplier_lead_time_days && <span className="text-slate-500">{sr.supplier_lead_time_days}d</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="min-h-screen bg-slate-50 animate-pulse">
      <div className="bg-white border-b border-slate-200 px-6 py-4"><div className="h-6 w-64 bg-slate-200 rounded" /></div>
      <div className="max-w-[1400px] mx-auto px-6 py-6 flex flex-col lg:flex-row gap-6">
        <div className="flex-1 space-y-5"><div className="bg-white rounded-lg p-5 h-48" /><div className="bg-white rounded-lg p-5 h-64" /><div className="bg-white rounded-lg p-5 h-32" /></div>
        <div className="w-72 space-y-4"><div className="bg-white rounded-lg p-4 h-28" /><div className="bg-white rounded-lg p-4 h-36" /><div className="bg-white rounded-lg p-4 h-28" /></div>
      </div>
    </div>
  );
}
