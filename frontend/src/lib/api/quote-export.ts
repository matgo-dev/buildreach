const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export async function exportQuotePdf(rfqId: number): Promise<void> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const resp = await fetch(
    `${API_BASE}/api/v1/rfqs/${rfqId}/quote/export`,
    {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    },
  );

  if (!resp.ok) {
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const body = await resp.json();
      throw new Error(body.message || "Export failed");
    }
    throw new Error(`Export failed: ${resp.status}`);
  }

  const blob = await resp.blob();
  const disposition = resp.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] || `Quotation_${rfqId}.pdf`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
