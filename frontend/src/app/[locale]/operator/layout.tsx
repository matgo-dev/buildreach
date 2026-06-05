import { OperatorShell } from "@/components/layout/OperatorShell";

export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return <OperatorShell>{children}</OperatorShell>;
}
