"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function AIToolsPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示 AI 智能体工具箱:标准问答、证书审查、报价比价、多语种翻译。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
