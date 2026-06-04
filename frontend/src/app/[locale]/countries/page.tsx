"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function CountriesPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示 8 国国别准入要求与认证清单。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
