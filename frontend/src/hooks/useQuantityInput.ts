"use client";

import { useCallback, useRef, useState } from "react";

interface UseQuantityInputOptions {
  initialValue: number;
  onCommit: (value: number) => void;
}

interface UseQuantityInputReturn {
  displayValue: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onBlur: () => void;
  reset: (value: number) => void;
  committedValue: number;
}

export function useQuantityInput({
  initialValue,
  onCommit,
}: UseQuantityInputOptions): UseQuantityInputReturn {
  const [displayValue, setDisplayValue] = useState(String(initialValue));
  const lastGoodRef = useRef(initialValue);
  const onCommitRef = useRef(onCommit);
  onCommitRef.current = onCommit;

  const onChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    setDisplayValue(raw);
    const num = parseFloat(raw);
    if (!isNaN(num) && num > 0) {
      lastGoodRef.current = num;
      onCommitRef.current(num);
    }
  }, []);

  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "-" || e.key === "e" || e.key === "E") {
      e.preventDefault();
    }
  }, []);

  const onBlur = useCallback(() => {
    const num = parseFloat(displayValue);
    if (isNaN(num) || num <= 0) {
      setDisplayValue(String(lastGoodRef.current));
    }
  }, [displayValue]);

  const reset = useCallback((value: number) => {
    lastGoodRef.current = value;
    setDisplayValue(String(value));
  }, []);

  return {
    displayValue,
    onChange,
    onKeyDown,
    onBlur,
    reset,
    committedValue: lastGoodRef.current,
  };
}
