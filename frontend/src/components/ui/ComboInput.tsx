"use client";

import { useCallback, useRef, useState } from "react";

interface ComboInputProps {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  className?: string;
}

/**
 * 可选可输的下拉输入框。
 * 预置选项列表 + 自由输入，适用于颜色、材质等半开放字段。
 */
export function ComboInput({ value, onChange, options, placeholder, className }: ComboInputProps) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 输入时同步筛选和值
  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    onChange(v);
    setFilter(v);
    setOpen(true);
  }, [onChange]);

  // 选中预置项
  const handleSelect = useCallback((opt: string) => {
    onChange(opt);
    setFilter("");
    setOpen(false);
    inputRef.current?.blur();
  }, [onChange]);

  // 点击外部关闭
  const handleBlur = useCallback((e: React.FocusEvent) => {
    if (!wrapperRef.current?.contains(e.relatedTarget as Node)) {
      setOpen(false);
      setFilter("");
    }
  }, []);

  const filtered = filter
    ? options.filter((o) => o.toLowerCase().includes(filter.toLowerCase()))
    : options;

  return (
    <div ref={wrapperRef} className="relative" onBlur={handleBlur}>
      <div className="flex">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInput}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className={className}
        />
        <button
          type="button"
          tabIndex={-1}
          onMouseDown={(e) => { e.preventDefault(); setOpen((o) => !o); inputRef.current?.focus(); }}
          className="absolute right-0 top-0 flex h-full w-7 items-center justify-center text-slate-400 hover:text-slate-600"
        >
          <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 5l3 3 3-3" />
          </svg>
        </button>
      </div>
      {open && filtered.length > 0 && (
        <ul className="absolute z-30 mt-0.5 max-h-40 w-full overflow-auto rounded-md border border-slate-200 bg-white py-0.5 shadow-lg">
          {filtered.map((opt) => (
            <li key={opt}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(opt)}
                className={`w-full px-2.5 py-1.5 text-left text-xs hover:bg-blue-50 ${
                  opt === value ? "bg-blue-50 font-medium text-blue-700" : "text-slate-700"
                }`}
              >
                {opt}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
