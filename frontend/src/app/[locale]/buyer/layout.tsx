import { BuyerShell } from "@/components/layout/BuyerShell";

export default function BuyerLayout({ children }: { children: React.ReactNode }) {
  return <BuyerShell>{children}</BuyerShell>;
}
