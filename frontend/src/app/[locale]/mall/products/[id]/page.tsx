"use client";

import { Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, Package } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";

function ProductDetailContent() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  return (
    <PublicLayout>
      <div className="rounded-xl border border-gray-200 bg-white py-20 text-center">
        <Package className="mx-auto mb-4 h-12 w-12 text-gray-300" />
        <h2 className="text-lg font-semibold text-gray-700">
          Product Detail — ID: {id}
        </h2>
        <p className="mt-2 text-sm text-gray-400">
          TODO: 商品详情页（含 SKU 选择器 + 询价篮）将在详情页工单中实现
        </p>
        <button
          onClick={() => router.back()}
          className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-[#0D4D4D] px-5 py-2 text-sm font-medium text-white hover:bg-[#0a3d3d] transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
      </div>
    </PublicLayout>
  );
}

export default function ProductDetailPage() {
  return (
    <RouteGuard allowRoles={["BUYER", "OPERATOR"]}>
      <Suspense fallback={null}>
        <ProductDetailContent />
      </Suspense>
    </RouteGuard>
  );
}
