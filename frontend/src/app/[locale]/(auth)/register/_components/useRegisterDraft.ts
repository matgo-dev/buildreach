"use client";

// SUPPLIER 3 步向导草稿持久化 hook(PRD v1.3 §2.3)。
//
// 行为约定:
// - mount 时一次性 hydrate(只取一次 sessionStorage)
// - 任何字段 update → 500ms debounce 后写 sessionStorage
// - 密码字段绝对不存(`password` / `confirmPassword`)
// - 关 tab 即清(sessionStorage tab 级)
// - 跨 tab 不串(sessionStorage tab 级)
// - 暴露 clearDraft():注册成功/切换角色时调用

import { useCallback, useEffect, useRef, useState } from "react";

import {
  DRAFT_STORAGE_KEY,
  type CountryCode,
  type LanguageCode,
} from "@/config/country-registration-rules";

export interface RegisterDraft {
  currentStep: 1 | 2 | 3;
  country_code: CountryCode | "";
  language_preference: LanguageCode | "";
  company_name: string;
  registration_no: string;
  name: string;
  phone: string;
  email: string;
  // 注意:password / confirmPassword 不在此结构中,任何路径下都不存
}

const EMPTY_DRAFT: RegisterDraft = {
  currentStep: 1,
  country_code: "",
  language_preference: "",
  company_name: "",
  registration_no: "",
  name: "",
  phone: "",
  email: "",
};

function readDraft(): RegisterDraft {
  if (typeof window === "undefined") return EMPTY_DRAFT;
  try {
    const raw = sessionStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return EMPTY_DRAFT;
    const parsed = JSON.parse(raw) as Partial<RegisterDraft>;
    // 防御:即使旧版本草稿里残留 password 字段,也丢弃
    return {
      ...EMPTY_DRAFT,
      ...parsed,
      currentStep: ([1, 2, 3].includes(parsed.currentStep as number)
        ? parsed.currentStep
        : 1) as 1 | 2 | 3,
    };
  } catch {
    return EMPTY_DRAFT;
  }
}

function writeDraft(draft: RegisterDraft) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // 隐私模式或 quota 异常时静默忽略,降级为内存态
  }
}

export function clearRegisterDraft() {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function useRegisterDraft() {
  const [draft, setDraft] = useState<RegisterDraft>(EMPTY_DRAFT);
  const [hydrated, setHydrated] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDraft(readDraft());
    setHydrated(true);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const update = useCallback((patch: Partial<RegisterDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => writeDraft(next), 500);
      return next;
    });
  }, []);

  const clearDraft = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setDraft(EMPTY_DRAFT);
    clearRegisterDraft();
  }, []);

  // PRD v1.4 Δ4:改国家时清字段 + 重置语言。
  // 其他字段(company_name / name / phone / email)保留,不受国家影响。
  const clearRegistrationNo = useCallback(() => {
    update({ registration_no: "" });
  }, [update]);

  const clearLanguagePreference = useCallback(() => {
    update({ language_preference: "" });
  }, [update]);

  return {
    draft,
    hydrated,
    update,
    clearDraft,
    clearRegistrationNo,
    clearLanguagePreference,
  };
}
