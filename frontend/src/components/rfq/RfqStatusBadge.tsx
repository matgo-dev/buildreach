"use client";

import { useTranslations } from "next-intl";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  SUBMITTED: "bg-blue-100 text-blue-700",
  PROCESSING: "bg-amber-100 text-amber-700",
  QUOTED: "bg-green-100 text-green-700",
  ACCEPTED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  EXPIRED: "bg-amber-100 text-amber-700",
  CANCELLED: "bg-gray-100 text-gray-500",
};

export function RfqStatusBadge({ status }: { status: string }) {
  const t = useTranslations("rfq");
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.DRAFT;

  let label: string;
  try {
    label = t(`status_${status}` as Parameters<typeof t>[0]);
  } catch {
    label = status;
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      {label}
    </span>
  );
}
