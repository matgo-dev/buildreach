"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, ChevronUp, Check } from "lucide-react";

interface FilterPanelProps {
  label: string;
  items: { key: string; label: string }[];
  /** 当前已选中的品牌（单选或多选确认后） */
  selected: string[];
  /** 单选模式：点击直接筛选 */
  onSelect: (key: string) => void;
  /** 多选模式：确认后回调（不传则不显示多选按钮） */
  onMultiSelect?: (keys: string[]) => void;
  allLabel?: string;
  onClearAll?: () => void;
  /** 是否显示总数标签，默认 false */
  showCount?: boolean;
}

/**
 * 品牌筛选面板 — 参考鑫方盛交互:
 * - 默认折叠一行，点"更多"展开
 * - 默认单选模式：点品牌直接筛选
 * - 点"多选"进入复选框模式：勾选 → 确定/取消
 */
export function FilterPanel({
  label,
  items,
  selected,
  onSelect,
  onMultiSelect,
  allLabel,
  onClearAll,
  showCount = false,
}: FilterPanelProps) {
  const t = useTranslations("mall");
  const containerRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const [multiMode, setMultiMode] = useState(false);
  // 多选模式下的临时勾选
  const [pending, setPending] = useState<Set<string>>(new Set());

  // 检测内容是否溢出一行
  const checkOverflow = useCallback(() => {
    const el = containerRef.current;
    if (el) {
      setOverflows(el.scrollHeight > el.clientHeight + 4);
    }
  }, []);

  useEffect(() => {
    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [checkOverflow, items]);

  const isAllSelected = selected.length === 0;

  // 进入多选模式
  const enterMultiMode = () => {
    setMultiMode(true);
    setExpanded(true);
    setPending(new Set(selected));
  };

  // 取消多选
  const cancelMulti = () => {
    setMultiMode(false);
    setPending(new Set());
  };

  // 确认多选
  const confirmMulti = () => {
    onMultiSelect?.(Array.from(pending));
    setMultiMode(false);
    setPending(new Set());
  };

  // 多选模式下切换勾选
  const togglePending = (key: string) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="flex items-start gap-2 sm:gap-3 px-3 sm:px-5 py-2.5">
      {/* 左侧标签 */}
      <span className="text-[12px] font-semibold text-gray-500 whitespace-nowrap pt-1.5 min-w-[48px]">
        {label}
      </span>

      {/* 中间: 选项区 */}
      <div className="flex-1 min-w-0">
        <div
          ref={containerRef}
          className={`flex flex-wrap gap-1 transition-all duration-200 ${
            expanded ? "max-h-[150px] sm:max-h-[500px] overflow-y-auto" : "max-h-[34px] overflow-hidden"
          }`}
        >
          {/* "全部"选项 */}
          {allLabel && !multiMode && (
            <button
              onClick={onClearAll}
              className={`h-[28px] rounded-md px-2.5 text-[12px] font-medium transition-all ${
                isAllSelected
                  ? "text-teal-700 font-bold"
                  : "text-ink hover:text-teal-700"
              }`}
            >
              {allLabel}
            </button>
          )}

          {items.map((item) => {
            const isSelected = selected.includes(item.key);
            const isPending = pending.has(item.key);

            if (multiMode) {
              // 复选框模式
              return (
                <label
                  key={item.key}
                  className="flex items-center gap-1 h-[28px] px-2 text-[12px] cursor-pointer hover:text-teal-700 transition-colors"
                >
                  <span
                    className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-all ${
                      isPending
                        ? "bg-teal-700 border-teal-700"
                        : "border-gray-300"
                    }`}
                    onClick={() => togglePending(item.key)}
                  >
                    {isPending && <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />}
                  </span>
                  <span
                    onClick={() => togglePending(item.key)}
                    className={isPending ? "text-teal-700 font-medium" : "text-ink"}
                  >
                    {item.label}
                  </span>
                </label>
              );
            }

            // 单选模式
            return (
              <button
                key={item.key}
                onClick={() => onSelect(item.key)}
                className={`h-[28px] rounded-md px-2.5 text-[12px] font-medium transition-all ${
                  isSelected
                    ? "text-teal-700 font-bold"
                    : "text-ink hover:text-teal-700"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        {/* 多选模式: 已选品牌 + 确定/取消 */}
        {multiMode && (
          <div className="mt-2 pt-2 border-t border-dashed border-gray-200 space-y-2">
            {pending.size > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[12px] text-gray-500 mr-1">{t("filterSelected")}</span>
                {Array.from(pending).map((k) => (
                  <span
                    key={k}
                    className="inline-flex items-center h-[22px] px-2 rounded-full bg-teal-50 text-[11px] font-medium text-teal-700 border border-teal-200"
                  >
                    {k}
                  </span>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={cancelMulti}
                className="h-[28px] rounded-md px-4 text-[12px] font-semibold border border-gray-300 text-ink hover:bg-gray-50 transition-colors"
              >
                {t("filterCancel")}
              </button>
              <button
                onClick={confirmMulti}
                className="h-[28px] rounded-md px-4 text-[12px] font-semibold bg-teal-700 text-white hover:bg-teal-800 transition-colors"
              >
                {t("filterConfirm")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 右侧: 更多/收起 + 多选或总数 */}
      <div className="flex items-center gap-2 whitespace-nowrap pt-1">
        {(overflows || expanded) && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-0.5 text-[12px] text-teal-700 hover:text-teal-900 font-medium transition-colors"
          >
            {expanded ? (
              <>
                {t("filterCollapse")}
                <ChevronUp className="h-3.5 w-3.5" />
              </>
            ) : (
              <>
                {t("filterMore")}
                <ChevronDown className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        )}
        {!multiMode && onMultiSelect && expanded ? (
          <button
            onClick={enterMultiMode}
            className="text-[12px] text-teal-700 hover:text-teal-900 font-medium border border-teal-200 rounded-md px-2 h-[24px] transition-colors"
          >
            {t("filterMultiSelect")}
          </button>
        ) : null}
        {showCount && items.length > 0 && (
          <span className="text-[11px] text-gray-400">
            {t("filterTotal", { count: items.length })}
          </span>
        )}
      </div>
    </div>
  );
}
