"use client";
import { useParams } from "next/navigation";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { CompanyDetailView } from "@/components/credit/CompanyDetailView";

export default function CreditCompanyDetailPage() {
  const params = useParams();
  const rawId = Array.isArray(params?.id) ? params!.id[0] : (params?.id as string);
  const companyId = parseInt(rawId, 10);
  if (Number.isNaN(companyId)) {
    return (
      <PublicLayout>
        <div className="rounded-xl border border-red-100 bg-red-50 p-8 text-center text-sm text-red-600">
          无效的企业 ID
        </div>
      </PublicLayout>
    );
  }
  return (
    <PublicLayout>
      <RouteGuard>
        <CompanyDetailView companyId={companyId} />
      </RouteGuard>
    </PublicLayout>
  );
}
