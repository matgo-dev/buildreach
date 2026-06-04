"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function RiskPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示风控驾驶舱:马甲关系图、价格异常监控、合规雷达。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
