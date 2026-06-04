"use client";
import { ReactNode } from "react";
import { useBootstrapAuth } from "@/hooks/useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  useBootstrapAuth();
  return <>{children}</>;
}
