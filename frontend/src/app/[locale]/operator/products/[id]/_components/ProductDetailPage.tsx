"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import useSWR from "swr";
import {
  ArrowLeft, Package, Edit3, TrendingUp, TrendingDown,
  Trash2, ChevronDown, ChevronRight, ChevronLeft, X, Loader2, AlertCircle, CheckCircle2,
} from "lucide-react";
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
  AggregateSkuInput,
  ImageRefInput,
} from "@/lib/api/operatorProducts";
import EditBasicInfo from "./EditBasicInfo";
import EditImages, { ImageChange } from "./EditImages";
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

  // 编辑态
  const [isEditing, setIsEditing] = useState(false);
  const [spuForm, setSpuForm] = useState<ProductUpdateInput>({});
  const [skuChanges, setSkuChanges] = useState<{ updated: Map<number, SkuFormData>; added: SkuFormData[]; removed: number[] }>({ updated: new Map(), added: [], removed: [] });
  const [imageChange, setImageChange] = useState<ImageChange>({ added: [], removed: [], newMainId: null, newOrder: null });
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [skuTemplates, setSkuTemplates] = useState<AttrTemplate[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [skuModalOpen, setSkuModalOpen] = useState(false);
  const [skuModalData, setSkuModalData] = useState<{ sku: SkuOperatorDetail | null; isNew: boolean }>({ sku: null, isNew: true });
  const [discardModal, setDiscardModal] = useState(false);
  const [confirmModal, setConfirmModal] = useState<{ type: "publish" | "unpublish" | "delete"; loading: boolean } | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [actionError, setActionError] = useState<{ message: string; errors?: string[] } | null>(null);
  const [expandedSkus, setExpandedSkus] = useState<Set<number>>(new Set());
  const [lightbox, setLightbox] = useState<{ images: { url: string }[]; index: number } | null>(null);

  const toggleSkuExpand = (skuId: number) => {
    setExpandedSkus((prev) => { const next = new Set(prev); if (next.has(skuId)) next.delete(skuId); else next.add(skuId); return next; });
  };

  // 进入编辑态
  const enterEditMode = useCallback(() => {
    if (!product) return;
    setSpuForm({
      name: locale === "en" ? product.name_en : product.name_zh || product.name,
      description: locale === "en" ? product.description_en : product.description_zh || product.description,
      brand: locale === "en" ? product.brand_en : product.brand_zh || product.brand,
      origin: locale === "en" ? product.origin_en : product.origin_zh || product.origin,
      hs_code: product.hs_code,
      certifications: product.certifications || [],
      selling_points: locale === "en" ? product.selling_points_en : product.selling_points_zh || product.selling_points,
      is_featured: product.is_featured,
      attributes: product.attributes.filter((a) => a.sku_id == null).map((a) => ({ attr_key: a.attr_key, attr_value: a.attr_value })),
    });
    setSkuChanges({ updated: new Map(), added: [], removed: [] });
    setImageChange({ added: [], removed: [], newMainId: null, newOrder: null });
    setImagePreviews([]);
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

  useEffect(() => {
    const urls = imageChange.added.map((f) => URL.createObjectURL(f));
    setImagePreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [imageChange.added]);

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 4000); return () => clearTimeout(t); } }, [toast]);

  // i18n 字段取值
  const localized = useCallback(
    (zhVal: string | null, enVal: string | null, fallback?: string | null) => {
      if (locale === "en") return enVal || zhVal || fallback || "";
      return zhVal || enVal || fallback || "";
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

  // 取消编辑
  const cancelEdit = () => {
    const hasChanges = skuChanges.updated.size > 0 || skuChanges.added.length > 0 || skuChanges.removed.length > 0 || imageChange.added.length > 0 || imageChange.removed.length > 0;
    if (hasChanges) setDiscardModal(true);
    else setIsEditing(false);
  };

  // 保存（单事务聚合）
  const handleSave = async () => {
    if (!product) return;
    // 前端预校验：必填项
    const validationErrors: string[] = [];
    if (!spuForm.name?.trim()) validationErrors.push(t("validationNameRequired"));
    for (const sku of skuChanges.added) {
      if (!sku.unit) validationErrors.push(t("validationSkuUnitRequired"));
      if (!sku.moq || sku.moq <= 0) validationErrors.push(t("validationSkuMoqRequired"));
    }
    if (validationErrors.length > 0) {
      setSaveError(validationErrors.join("；"));
      return;
    }
    setSaving(true); setSaveError(null);
    try {
      // 先处理图片上传/删除（图片文件操作在聚合事务外）
      for (const [skuId, data] of skuChanges.updated) {
        for (const imgId of data.removedImageIds) await operatorProductsApi.deleteImage(product.id, imgId);
        for (const file of data.imageFiles) await operatorProductsApi.uploadImage(product.id, file, skuId);
      }
      for (const file of imageChange.added) await operatorProductsApi.uploadImage(product.id, file);
      for (const imgId of imageChange.removed) await operatorProductsApi.deleteImage(product.id, imgId);

      // 组装「期望完整态」SKU 列表：保留的 + 新增的
      const aggregateSkus: AggregateSkuInput[] = [];

      // 已有 SKU（未删除的）
      for (const sku of product.skus) {
        if (skuChanges.removed.includes(sku.id)) continue;
        const updated = skuChanges.updated.get(sku.id);
        if (updated) {
          aggregateSkus.push({
            id: sku.id,
            manufacturer_model: updated.manufacturer_model,
            name: updated.name,
            color: updated.color,
            material: updated.material,
            price_min: updated.price_min,
            price_max: updated.price_max,
            currency: updated.currency,
            unit: updated.unit as AggregateSkuInput["unit"],
            moq: updated.moq!,
            lead_time_min: updated.lead_time_min,
            lead_time_max: updated.lead_time_max,
            packing_quantity: updated.packing_quantity,
            gross_weight_kg: updated.gross_weight_kg,
            volume_cbm: updated.volume_cbm,
            can_consolidate: updated.can_consolidate,
            cargo_type: updated.cargo_type,
            is_default: updated.is_default,
            price_tiers: updated.price_tiers,
            attributes: updated.attributes,
          });
        } else {
          // 未修改的 SKU，原样传入（带 id 表示保留）
          aggregateSkus.push({
            id: sku.id,
            manufacturer_model: sku.manufacturer_model,
            name: locale === "en" ? sku.name_en : sku.name_zh || sku.name,
            color: locale === "en" ? sku.color_en : sku.color_zh || sku.color,
            material: locale === "en" ? sku.material_en : sku.material_zh || sku.material,
            price_min: sku.price_min ? Number(sku.price_min) : undefined,
            price_max: sku.price_max ? Number(sku.price_max) : undefined,
            currency: sku.currency,
            unit: sku.unit as AggregateSkuInput["unit"],
            moq: sku.moq,
            lead_time_min: sku.lead_time_min,
            lead_time_max: sku.lead_time_max,
            packing_quantity: sku.packing_quantity,
            gross_weight_kg: sku.gross_weight_kg ? Number(sku.gross_weight_kg) : undefined,
            volume_cbm: sku.volume_cbm ? Number(sku.volume_cbm) : undefined,
            can_consolidate: sku.can_consolidate,
            cargo_type: sku.cargo_type,
            is_default: sku.is_default,
            price_tiers: sku.price_tiers.map((pt) => ({ min_qty: pt.min_qty, max_qty: pt.max_qty, unit_price: Number(pt.unit_price), currency: pt.currency })),
            attributes: sku.attributes.map((a) => ({ attr_key: a.attr_key, attr_value: a.attr_value })),
          });
        }
      }

      // 新增的 SKU（无 id）
      for (const added of skuChanges.added) {
        aggregateSkus.push({
          manufacturer_model: added.manufacturer_model,
          name: added.name,
          color: added.color,
          material: added.material,
          price_min: added.price_min,
          price_max: added.price_max,
          currency: added.currency,
          unit: added.unit as AggregateSkuInput["unit"],
          moq: added.moq!,
          lead_time_min: added.lead_time_min,
          lead_time_max: added.lead_time_max,
          packing_quantity: added.packing_quantity,
          gross_weight_kg: added.gross_weight_kg,
          volume_cbm: added.volume_cbm,
          can_consolidate: added.can_consolidate,
          cargo_type: added.cargo_type,
          is_default: added.is_default,
          price_tiers: added.price_tiers,
          attributes: added.attributes,
        });
      }

      // 图片引用（从最新的服务端图片列表 + 本地变更推算）
      // 重新 fetch 图片状态由 mutate 处理；这里只做 主图/排序 引用
      let imageRefs: ImageRefInput[] | undefined;
      if (imageChange.newMainId || imageChange.newOrder) {
        // 构建当前有效图片引用
        const currentImages = product.images.filter((img) => !imageChange.removed.includes(img.id));
        const ordered = imageChange.newOrder
          ? imageChange.newOrder.map((id) => currentImages.find((img) => img.id === id)).filter(Boolean) as ProductImage[]
          : currentImages;
        imageRefs = ordered.map((img, idx) => ({
          image_id: img.id,
          image_type: (imageChange.newMainId === img.id ? "MAIN" : img.image_type === "MAIN" && imageChange.newMainId ? "GALLERY" : img.image_type) as ImageRefInput["image_type"],
          sort_order: idx,
        }));
      }

      // 一次聚合保存
      await operatorProductsApi.saveAggregate(product.id, {
        name: spuForm.name,
        description: spuForm.description,
        origin: spuForm.origin,
        hs_code: spuForm.hs_code,
        brand: spuForm.brand,
        certifications: spuForm.certifications,
        selling_points: spuForm.selling_points,
        is_featured: spuForm.is_featured,
        attributes: spuForm.attributes,
        skus: aggregateSkus,
        images: imageRefs,
      });

      await mutate();
      setIsEditing(false);
      setToast({ message: t("saveSuccess"), type: "success" });
      if (searchParams.get("edit")) {
        router.replace(`/${locale}/operator/products/${product.id}`, { scroll: false });
      }
    } catch (err: unknown) {
      setSaveError(translateError(err));
    } finally { setSaving(false); }
  };

  // 状态操作
  const handleStatusAction = async () => {
    if (!confirmModal || !product) return;
    setConfirmModal({ ...confirmModal, loading: true }); setActionError(null);
    try {
      if (confirmModal.type === "delete") {
        await operatorProductsApi.remove(product.id);
        setToast({ message: tList("toastDeleted"), type: "success" });
        setTimeout(() => router.push(`/${locale}/operator/products`), 500);
      } else {
        const newStatus = confirmModal.type === "publish" ? "ACTIVE" : "INACTIVE";
        await operatorProductsApi.updateStatus(product.id, { status: newStatus });
        setToast({ message: confirmModal.type === "publish" ? tList("toastPublished") : tList("toastUnpublished"), type: "success" });
        await mutate();
      }
      setConfirmModal(null);
    } catch (err: unknown) {
      // 解析上架校验错误列表
      if (err instanceof ApiError && err.messageParams && Array.isArray(err.messageParams.errors)) {
        setActionError({ message: translateError(err), errors: err.messageParams.errors as string[] });
      } else {
        setActionError({ message: translateError(err) });
      }
      setConfirmModal({ ...confirmModal, loading: false });
    }
  };

  // SKU Modal
  const openSkuModal = (sku: SkuOperatorDetail | null, isNew: boolean) => { setSkuModalData({ sku, isNew }); setSkuModalOpen(true); };
  const handleSkuModalConfirm = (data: SkuFormData) => {
    if (skuModalData.isNew) setSkuChanges((prev) => ({ ...prev, added: [...prev.added, data] }));
    else if (skuModalData.sku) setSkuChanges((prev) => { const updated = new Map(prev.updated); updated.set(skuModalData.sku!.id, data); return { ...prev, updated }; });
    setSkuModalOpen(false);
  };
  const handleSkuDelete = (skuId: number) => {
    setSkuChanges((prev) => ({ ...prev, removed: [...prev.removed, skuId], updated: (() => { const m = new Map(prev.updated); m.delete(skuId); return m; })() }));
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
                <button onClick={cancelEdit} disabled={saving} className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">{t("cancelEdit")}</button>
                <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60">
                  {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{t("save")}
                </button>
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
            <EditBasicInfo product={product} value={spuForm} onChange={setSpuForm} />
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
                {t("skuVariants")} <span className="text-slate-400 font-normal">({product.skus.filter((s) => !skuChanges.removed.includes(s.id)).length + skuChanges.added.length})</span>
              </h3>
              {isEditing && <button type="button" onClick={() => openSkuModal(null, true)} className="text-xs text-blue-600 hover:text-blue-700 font-medium">+ {t("addSku")}</button>}
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
                  {product.skus.filter((s) => !skuChanges.removed.includes(s.id)).map((sku) => (
                    <SkuRow key={sku.id} sku={sku} locale={locale} localized={localized} expanded={expandedSkus.has(sku.id)} onToggle={() => toggleSkuExpand(sku.id)} t={t} isEditing={isEditing} onEdit={() => openSkuModal(sku, false)} onDelete={() => handleSkuDelete(sku.id)} />
                  ))}
                  {skuChanges.added.map((added, i) => (
                    <tr key={`new-${i}`} className="border-b border-slate-50 bg-blue-50/30">
                      <td className="px-3 py-2.5"><span className="font-mono text-slate-700">{added.sku_code || "(auto)"}</span><span className="ml-1.5 bg-blue-100 text-blue-600 text-[9px] px-1.5 py-0.5 rounded">NEW</span></td>
                      <td className="px-3 py-2.5 text-slate-600">{[added.color, added.material, added.unit].filter(Boolean).join(" / ")}</td>
                      <td className="px-3 py-2.5 text-right text-slate-800 font-medium">{added.price_min || added.price_max ? `${added.currency} ${added.price_min ?? "?"} - ${added.price_max ?? "?"}` : "—"}</td>
                      <td className="px-3 py-2.5 text-right text-slate-600">{added.moq}</td>
                      <td className="px-3 py-2.5 text-center"><span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700">Active</span></td>
                      <td className="px-3 py-2.5 text-center"><button onClick={() => setSkuChanges((prev) => ({ ...prev, added: prev.added.filter((_, j) => j !== i) }))} className="text-red-500 hover:text-red-700"><X className="h-3.5 w-3.5" /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {product.skus.filter((s) => !skuChanges.removed.includes(s.id)).length === 0 && skuChanges.added.length === 0 && (
                <div className="text-center py-8 text-slate-400 text-sm">{t("noSkus")}</div>
              )}
            </div>
          </section>

          {/* 商品图片 */}
          {isEditing ? (
            <div id="image-section">
              <EditImages images={product.images} imageChange={imageChange} onChange={setImageChange} previews={imagePreviews} />
            </div>
          ) : (
            <section id="image-section" className="bg-white rounded-lg shadow-sm p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4">{t("productImages")} <span className="text-slate-400 font-normal">({product.images.length}/8)</span></h3>
              <div className="flex flex-wrap gap-3">
                {product.images.map((img, idx) => (
                  <div
                    key={img.id}
                    className={`relative w-24 h-24 rounded-lg overflow-hidden border-2 cursor-pointer hover:shadow-md transition-shadow ${img.image_type === "MAIN" ? "border-blue-500" : "border-slate-200"} bg-slate-100`}
                    onClick={() => setLightbox({ images: product.images.map((i) => ({ url: i.full_url })), index: idx })}
                  >
                    <img src={img.full_url} alt="" className="w-full h-full object-cover" loading="lazy" />
                    {img.image_type === "MAIN" && <span className="absolute top-0 left-0 bg-blue-500 text-white text-[10px] px-1.5 py-0.5 rounded-br">{t("mainImage")}</span>}
                  </div>
                ))}
                {product.images.length === 0 && <div className="text-slate-400 text-sm">{t("noImages")}</div>}
              </div>
            </section>
          )}

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
              <div className="flex justify-between"><span className="text-slate-400">{t("priceRange")}</span><span className="text-slate-700 font-medium">{formatPrice(product.skus.reduce((min, s) => s.price_min != null ? Math.min(min, Number(s.price_min)) : min, Infinity) === Infinity ? null : product.skus.reduce((min, s) => s.price_min != null ? Math.min(min, Number(s.price_min)) : min, Infinity), product.skus.reduce((max, s) => s.price_max != null ? Math.max(max, Number(s.price_max)) : max, -Infinity) === -Infinity ? null : product.skus.reduce((max, s) => s.price_max != null ? Math.max(max, Number(s.price_max)) : max, -Infinity), product.skus[0]?.currency || "TZS")}</span></div>
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
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md bg-white rounded-xl p-6 shadow-2xl mx-4">
            {actionError ? (
              <>
                {/* 校验失败态：展示错误 + 引导去编辑 */}
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
                    // 根据错误类型决定滚动目标
                    const errors = actionError?.errors || [];
                    const hasSkuErr = errors.some((e) => e.toLowerCase().includes("sku") || e.toLowerCase().includes("price"));
                    const hasImgErr = errors.some((e) => e.toLowerCase().includes("image"));
                    setConfirmModal(null); setActionError(null); enterEditMode();
                    // 进入编辑态后滚动到问题区域
                    setTimeout(() => {
                      const target = hasSkuErr ? "sku-section" : hasImgErr ? "image-section" : null;
                      if (target) document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "center" });
                    }, 100);
                  }} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">{t("goEdit")}</button>
                </div>
              </>
            ) : (
              <>
                {/* 正常确认态 */}
                <h3 className="text-base font-semibold text-slate-900 mb-2">
                  {confirmModal.type === "publish" && tList("confirmPublishTitle")}
                  {confirmModal.type === "unpublish" && tList("confirmUnpublishTitle")}
                  {confirmModal.type === "delete" && tList("confirmDeleteTitle")}
                </h3>
                <p className="text-sm text-slate-600 mb-4 whitespace-pre-line">
                  {confirmModal.type === "publish" && tList("confirmPublishMsg", { name: product.name })}
                  {confirmModal.type === "unpublish" && tList("confirmUnpublishMsg", { name: product.name })}
                  {confirmModal.type === "delete" && tList("confirmDeleteMsg", { name: product.name })}
                </p>
                <div className="flex justify-end gap-2">
                  <button onClick={() => { setConfirmModal(null); setActionError(null); }} className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50" disabled={confirmModal.loading}>{tList("cancel")}</button>
                  <button onClick={handleStatusAction} disabled={confirmModal.loading} className={`px-4 py-2 text-sm rounded-lg text-white flex items-center gap-1.5 ${confirmModal.type === "publish" ? "bg-emerald-600 hover:bg-emerald-700" : confirmModal.type === "unpublish" ? "bg-amber-600 hover:bg-amber-700" : "bg-red-600 hover:bg-red-700"} disabled:opacity-60`}>
                    {confirmModal.loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {confirmModal.type === "publish" && tList("confirmPublishBtn")}
                    {confirmModal.type === "unpublish" && tList("confirmUnpublishBtn")}
                    {confirmModal.type === "delete" && tList("confirmDeleteBtn")}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 放弃修改确认 */}
      {discardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm bg-white rounded-xl p-6 shadow-2xl mx-4">
            <h3 className="text-base font-semibold text-slate-900 mb-2">{t("confirmDiscardTitle")}</h3>
            <p className="text-sm text-slate-600 mb-4">{t("confirmDiscardMsg")}</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDiscardModal(false)} className="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">{tList("cancel")}</button>
              <button onClick={() => { setDiscardModal(false); setIsEditing(false); }} className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700">{t("confirmDiscard")}</button>
            </div>
          </div>
        </div>
      )}

      {/* SKU Modal */}
      <SkuEditModal
        open={skuModalOpen} onClose={() => setSkuModalOpen(false)} onConfirm={handleSkuModalConfirm} isNew={skuModalData.isNew} skuTemplates={skuTemplates}
        initial={skuModalData.sku ? { sku_code: skuModalData.sku.sku_code, manufacturer_model: skuModalData.sku.manufacturer_model, name: locale === "en" ? skuModalData.sku.name_en : skuModalData.sku.name_zh || skuModalData.sku.name, color: locale === "en" ? skuModalData.sku.color_en : skuModalData.sku.color_zh || skuModalData.sku.color, material: locale === "en" ? skuModalData.sku.material_en : skuModalData.sku.material_zh || skuModalData.sku.material, price_min: skuModalData.sku.price_min ? Number(skuModalData.sku.price_min) : null, price_max: skuModalData.sku.price_max ? Number(skuModalData.sku.price_max) : null, currency: skuModalData.sku.currency, unit: skuModalData.sku.unit, moq: skuModalData.sku.moq, lead_time_min: skuModalData.sku.lead_time_min, lead_time_max: skuModalData.sku.lead_time_max, packing_quantity: skuModalData.sku.packing_quantity, gross_weight_kg: skuModalData.sku.gross_weight_kg ? Number(skuModalData.sku.gross_weight_kg) : null, volume_cbm: skuModalData.sku.volume_cbm ? Number(skuModalData.sku.volume_cbm) : null, can_consolidate: skuModalData.sku.can_consolidate, cargo_type: skuModalData.sku.cargo_type, is_default: skuModalData.sku.is_default, status: skuModalData.sku.status, price_tiers: skuModalData.sku.price_tiers.map((pt) => ({ min_qty: pt.min_qty, max_qty: pt.max_qty, unit_price: Number(pt.unit_price), currency: pt.currency })), attributes: skuModalData.sku.attributes.map((a) => ({ attr_key: a.attr_key, attr_value: a.attr_value })), imageFiles: [], existingImages: skuModalData.sku.images.map((img) => ({ id: img.id, url: img.full_url })), removedImageIds: [] } : null}
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

      {/* Toast — 顶部居中悬浮 */}
      {toast && (
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-50 rounded-lg px-5 py-3 text-sm font-medium shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2 ${
          toast.type === "success" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-800 border border-red-200"
        }`}>
          {toast.type === "success" ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <AlertCircle className="h-4 w-4 text-red-500" />}
          {toast.message}
          <button onClick={() => setToast(null)} className="ml-2 hover:opacity-70"><X className="h-3.5 w-3.5" /></button>
        </div>
      )}
    </div>
  );
}

// 子组件
function FieldDisplay({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (<div><span className="text-slate-400 text-xs">{label}</span><div className={`mt-0.5 text-slate-800 text-sm ${mono ? "font-mono" : ""}`}>{value || "—"}</div></div>);
}

function SkuRow({ sku, locale, localized, expanded, onToggle, t, isEditing, onEdit, onDelete }: {
  sku: SkuOperatorDetail; locale: string; localized: (zh: string | null, en: string | null, fallback?: string | null) => string;
  expanded: boolean; onToggle: () => void; t: ReturnType<typeof useTranslations>; isEditing?: boolean; onEdit?: () => void; onDelete?: () => void;
}) {
  const skuStatus = sku.status === "ACTIVE" ? { bg: "bg-emerald-50", text: "text-emerald-700", label: t("skuStatusActive") } : { bg: "bg-slate-100", text: "text-slate-600", label: t("skuStatusInactive") };
  const specs = [localized(sku.color_zh, sku.color_en, sku.color), localized(sku.material_zh, sku.material_en, sku.material), sku.unit].filter(Boolean).join(" / ");
  return (
    <>
      <tr className="border-b border-slate-50 hover:bg-slate-50/50">
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
        <td className="px-3 py-2.5 text-right text-slate-800 font-medium">{formatPrice(sku.price_min ? Number(sku.price_min) : null, sku.price_max ? Number(sku.price_max) : null, sku.currency)}</td>
        <td className="px-3 py-2.5 text-right text-slate-600">{sku.moq} {sku.unit?.toLowerCase()}</td>
        <td className="px-3 py-2.5 text-center"><span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${skuStatus.bg} ${skuStatus.text}`}>{skuStatus.label}</span></td>
        <td className="px-3 py-2.5 text-center">
          {isEditing ? (
            <div className="flex items-center justify-center gap-2">
              <button onClick={onEdit} className="text-blue-600 hover:text-blue-700 text-[11px] font-medium">{t("edit")}</button>
              <button onClick={onDelete} className="text-red-500 hover:text-red-700 text-[11px] font-medium">{t("deleteSku")}</button>
            </div>
          ) : <button onClick={onToggle} className="text-slate-400 hover:text-slate-600">{expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button>}
        </td>
      </tr>
      {expanded && !isEditing && (
        <tr className="bg-slate-50/70"><td colSpan={6} className="px-6 py-4"><SkuExpandedDetails sku={sku} locale={locale} t={t} /></td></tr>
      )}
    </>
  );
}

function SkuExpandedDetails({ sku, locale, t }: { sku: SkuOperatorDetail; locale: string; t: ReturnType<typeof useTranslations> }) {
  const loc = (zh: string | null, en: string | null, fb?: string | null) => locale === "en" ? (en || zh || fb || "") : (zh || en || fb || "");
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
        <div><span className="text-slate-400">{t("currency")}</span><div className="mt-0.5"><Val v={sku.currency} /></div></div>
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
                  <td className="py-1.5 text-slate-600">{tier.min_qty}{tier.max_qty ? ` - ${tier.max_qty}` : "+"} {sku.unit?.toLowerCase()}</td>
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
                {sku.images.map((img) => (
                  <div key={img.id} className="w-16 h-16 rounded border border-slate-200 overflow-hidden bg-slate-50">
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
