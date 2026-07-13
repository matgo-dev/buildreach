"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Calculator, Check, ChevronLeft, Loader2, RotateCcw, Scale, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { MarkdownLite } from "./Markdown";
import { CopyButton } from "./CopyButton";
import {
  calcLandedCost,
  compareLocalVsImport,
  detectCategory,
  getCategory,
  LOCAL_TRANSPORT_TABLE,
  RATES,
  TANZANIA_TAX_TABLE,
  type ComparisonResult,
  type CostBreakdown,
  type CostInput,
  type PriceBasis,
} from "./costCalculator";

const HEADER_BG = "linear-gradient(120deg, #0a7a56, #0c9468 60%, #10b981)";
const ACCENT_BG = "linear-gradient(120deg, #0a7a56, #10b981)";

const CITY_KEYS = Object.keys(LOCAL_TRANSPORT_TABLE);
const BASES: PriceBasis[] = ["EXW", "FOB", "CIF"];

/** 流式"思考"步骤(演示用,营造 AI 测算过程感) */
const COST_STEPS = ["stepMatch", "stepTax", "stepLogi", "stepResult"];
const COMPARE_STEPS = ["stepMatch", "stepTax", "stepLogi", "stepLocal", "stepCompare"];

/** 演示默认值:500 箱瓷砖发达累斯萨拉姆 */
const DEMO_FORM: FormState = {
  product: "",
  categoryId: "tiles",
  basis: "FOB",
  unitPrice: "8",
  quantity: "500",
  unitWeightKg: "32",
  unitVolumeCbm: "0.033",
  destCity: "dar",
};

interface FormState {
  product: string;
  categoryId: string;
  basis: PriceBasis;
  unitPrice: string;
  quantity: string;
  unitWeightKg: string;
  unitVolumeCbm: string;
  destCity: string;
}

interface Result {
  input: CostInput;
  breakdown: CostBreakdown;
  comparison: ComparisonResult | null;
}

export function CostCalculatorDialog({
  mode = "cost",
  onClose,
}: {
  mode?: "cost" | "compare";
  onClose: () => void;
}) {
  const t = useTranslations("aiAssistant");
  const compareMode = mode === "compare";
  const [form, setForm] = useState<FormState>(DEMO_FORM);
  const [result, setResult] = useState<Result | null>(null);
  const [thinking, setThinking] = useState(false);
  const [thinkStep, setThinkStep] = useState(0);
  const pendingRef = useRef<Result | null>(null);

  const steps = compareMode ? COMPARE_STEPS : COST_STEPS;
  const stepCount = steps.length;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // 流式"思考":逐步打勾,结束后揭示结果(演示真实感)
  useEffect(() => {
    if (!thinking) return;
    let step = 0;
    setThinkStep(0);
    const iv = setInterval(() => {
      step += 1;
      setThinkStep(step);
      if (step >= stepCount) {
        clearInterval(iv);
        window.setTimeout(() => {
          setResult(pendingRef.current);
          setThinking(false);
        }, 300);
      }
    }, 340);
    return () => clearInterval(iv);
  }, [thinking, stepCount]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  // 输入产品名自动匹配品类
  function onProductChange(text: string) {
    const hit = detectCategory(text);
    setForm((f) => ({ ...f, product: text, categoryId: hit ? hit.id : f.categoryId }));
  }

  // 比价助手:只需数量;成本测算:需单价、数量、体积。
  const canCalc = compareMode
    ? Number(form.quantity) > 0
    : Number(form.unitPrice) > 0 && Number(form.quantity) > 0 && Number(form.unitVolumeCbm) > 0;

  function handleCalc() {
    if (!canCalc) return;
    const cat = getCategory(form.categoryId);
    const quantity = Number(form.quantity);
    // 比价模式:单价与体积用品类内置参考值(用户只选商品+数量+目的城市)。
    const input: CostInput = compareMode
      ? {
          categoryId: form.categoryId,
          basis: "FOB",
          unitPrice: cat.refFobUnitPrice,
          quantity,
          unitWeightKg: 0,
          unitVolumeCbm: cat.refUnitVolumeCbm,
          destCity: form.destCity,
        }
      : {
          categoryId: form.categoryId,
          basis: form.basis,
          unitPrice: Number(form.unitPrice),
          quantity,
          unitWeightKg: Number(form.unitWeightKg) || 0,
          unitVolumeCbm: Number(form.unitVolumeCbm),
          destCity: form.destCity,
        };
    const breakdown = calcLandedCost(input);
    // 对比仅在比价助手(compare)中进行;成本测算助手只做进口到岸/到场拆解。
    const comparison = compareMode ? compareLocalVsImport(input, breakdown) : null;
    // 先走"思考"流,再揭示结果
    pendingRef.current = { input, breakdown, comparison };
    setResult(null);
    setThinking(true);
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm sm:p-4">
      <div className="flex h-[92vh] sm:h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl bg-white shadow-2xl">
        {/* 顶栏 */}
        <div className="flex items-center gap-3 px-4 sm:px-5 py-3.5 text-white" style={{ background: HEADER_BG }}>
          <button
            onClick={result ? () => setResult(null) : onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/15 hover:bg-white/25 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15">
            {compareMode ? <Scale className="h-4 w-4" /> : <Calculator className="h-4 w-4" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold truncate">
              {t(compareMode ? "localTitle" : "costCalcTitle")}
            </div>
            <div className="text-xs text-white/60">{t("dialogOnline")}</div>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/15 hover:bg-white/25 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto bg-[#f7f7f8] px-4 sm:px-6 py-5">
          {thinking ? (
            <ThinkingView steps={steps} current={thinkStep} t={t} />
          ) : result ? (
            <ResultView
              result={result}
              onReset={() => setResult(null)}
              compareMode={compareMode}
              t={t}
            />
          ) : (
            <FormView
              form={form}
              set={set}
              onProductChange={onProductChange}
              onCalc={handleCalc}
              canCalc={canCalc}
              compareMode={compareMode}
              t={t}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 表单步 ──────────────────────────────────────
function FormView({
  form,
  set,
  onProductChange,
  onCalc,
  canCalc,
  compareMode,
  t,
}: {
  form: FormState;
  set: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
  onProductChange: (text: string) => void;
  onCalc: () => void;
  canCalc: boolean;
  compareMode: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  const detected = form.product.trim() ? detectCategory(form.product) : null;

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <p className="text-sm text-ink-2 leading-relaxed">
        {t(compareMode ? "localIntro" : "costCalcIntro")}
      </p>

      <div>
        <Field label={t("ccProduct")}>
          <input
            value={form.product}
            onChange={(e) => onProductChange(e.target.value)}
            placeholder={t("ccProductPlaceholder")}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm focus:border-teal-400 focus:outline-none"
          />
        </Field>
        {form.product.trim() &&
          (detected ? (
            <div className="mt-1.5 flex items-center gap-1.5 text-xs text-teal-700">
              <Check className="h-3.5 w-3.5" />
              {t("ccDetected")}：{t(`cat_${detected.id}`)} · HS {detected.hsCode} · {t("line_duty")}{" "}
              {(detected.dutyPct * 100).toFixed(0)}%
            </div>
          ) : (
            <div className="mt-1.5 text-xs text-slate-400">{t("ccNoMatch")}</div>
          ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t("ccCategory")}>
          <Select value={form.categoryId} onChange={(v) => set("categoryId", v)}>
            {TANZANIA_TAX_TABLE.map((c) => (
              <option key={c.id} value={c.id}>
                {t(`cat_${c.id}`)}
              </option>
            ))}
          </Select>
        </Field>
        {!compareMode && (
          <Field label={t("ccBasis")}>
            <Select value={form.basis} onChange={(v) => set("basis", v as PriceBasis)}>
              {BASES.map((b) => (
                <option key={b} value={b}>
                  {t(`basis_${b}`)}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {!compareMode && (
          <Field label={t("ccUnitPrice")}>
            <NumInput value={form.unitPrice} onChange={(v) => set("unitPrice", v)} suffix="USD" />
          </Field>
        )}
        <Field label={t("ccQuantity")}>
          <NumInput value={form.quantity} onChange={(v) => set("quantity", v)} suffix={t("ccPcs")} />
        </Field>
        {!compareMode && (
          <Field label={t("ccUnitWeight")}>
            <NumInput value={form.unitWeightKg} onChange={(v) => set("unitWeightKg", v)} suffix="kg" />
          </Field>
        )}
        {!compareMode && (
          <Field label={t("ccUnitVolume")}>
            <NumInput value={form.unitVolumeCbm} onChange={(v) => set("unitVolumeCbm", v)} suffix="CBM" />
          </Field>
        )}
        <Field label={t("ccDestCity")}>
          <Select value={form.destCity} onChange={(v) => set("destCity", v)}>
            {CITY_KEYS.map((c) => (
              <option key={c} value={c}>
                {t(`city_${c}`)}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <button
        onClick={onCalc}
        disabled={!canCalc}
        className={
          "w-full rounded-xl py-3 text-sm font-bold text-white transition-all " +
          (canCalc ? "hover:opacity-90" : "cursor-not-allowed opacity-50")
        }
        style={{ background: ACCENT_BG }}
      >
        {t(compareMode ? "ccCompareBtn" : "ccCalcBtn")}
      </button>

      <p className="text-[11px] leading-relaxed text-slate-400">{t("ccDisclaimer")}</p>
    </div>
  );
}

// ─── 结果步 ──────────────────────────────────────
function ResultView({
  result,
  onReset,
  compareMode,
  t,
}: {
  result: Result;
  onReset: () => void;
  compareMode: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  const md = useMemo(() => buildMarkdown(result, t, compareMode), [result, t, compareMode]);
  const conclusion = useMemo(() => buildConclusion(result, t, compareMode), [result, t, compareMode]);
  const typed = useTypewriter(conclusion);
  const { breakdown, comparison } = result;

  return (
    <div className="mx-auto max-w-xl">
      {/* AI 结论/建议 */}
      <div className="mb-4 flex gap-2 rounded-2xl border border-teal-200 bg-teal-50 px-4 py-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
        <p className="text-sm leading-relaxed text-teal-900">
          {typed}
          {typed.length < conclusion.length && (
            <span className="ml-0.5 inline-block h-3.5 w-[2px] -mb-0.5 animate-pulse bg-teal-500 align-middle" />
          )}
        </p>
      </div>

      {/* 结果高亮卡 */}
      <div className="grid grid-cols-3 gap-3">
        {compareMode && comparison ? (
          <>
            <StatCard label={t("ccImport")} value={usd(comparison.importOnSite)} />
            <StatCard
              label={t("ccLocal")}
              value={usd(comparison.localOnSite)}
              highlight={comparison.cheaper === "local"}
            />
            <StatCard
              label={t("ccDelta")}
              value={(comparison.deltaTotal >= 0 ? "+" : "−") + usd(Math.abs(comparison.deltaTotal))}
            />
          </>
        ) : (
          <>
            <StatCard label={t("ccLandedPort")} value={usd(breakdown.landedAtPort)} />
            <StatCard label={t("ccLandedSite")} value={usd(breakdown.landedOnSite)} highlight />
            <StatCard label={t("ccUnitCost")} value={usd(breakdown.unitCost)} />
          </>
        )}
      </div>

      <div className="mt-4 rounded-2xl bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm">
        <MarkdownLite text={md} />
      </div>

      <div className="mt-2 flex justify-start">
        <CopyButton text={`${conclusion}\n\n${md}`} variant="ghost" />
      </div>

      <button
        onClick={onReset}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-3 text-sm font-bold text-ink-2 transition-all hover:border-teal-300 hover:text-teal-800"
      >
        <RotateCcw className="h-4 w-4" />
        {t("ccRecalc")}
      </button>
    </div>
  );
}

// ─── 结果 → markdown ─────────────────────────────
function buildMarkdown(
  result: Result,
  t: (key: string, values?: Record<string, string | number>) => string,
  compareMode: boolean,
): string {
  const { breakdown: b, comparison: c, input } = result;
  const cat = b.category;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

  const goods = [
    `**${t("ccSecGoods")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColValue")} |`,
    "|------|------|",
    `| ${t("cat_" + cat.id)}（HS ${cat.hsCode}） | ${t("basis_" + input.basis)} |`,
    `| ${t("ccQuantity")} | ${input.quantity} ${t("ccPcs")} |`,
    `| ${t("ccTotalVolume")} | ${b.totalVolumeCbm} CBM |`,
    `| ${t("ccTotalWeight")} | ${b.totalWeightKg} kg |`,
    "",
  ];

  const price = [
    `**${t("ccSecPrice")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColAmount")} |`,
    "|------|------|",
    `| ${t("ccGoodsValue")} | ${usd(b.goodsValueAtBasis)} |`,
    ...(b.inlandChina > 0 ? [`| ${t("line_inlandChina")} | ${usd(b.inlandChina)} |`] : []),
    `| ${t("ccFob")} | ${usd(b.fobValue)} |`,
    `| ${t("line_freight")} | ${usd(b.freight)} |`,
    `| ${t("line_insurance")} | ${usd(b.insurance)} |`,
    `| **${t("ccCif")}** | **${usd(b.cifValue)}** |`,
    "",
  ];

  const tax = [
    `**${t("ccSecTax")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColRate")} | ${t("ccColAmount")} |`,
    "|------|------|------|",
    `| ${t("line_duty")} | ${pct(cat.dutyPct)} | ${usd(b.duty)} |`,
    `| ${t("line_rdl")} | ${pct(RATES.rdlPct)} | ${usd(b.rdl)} |`,
    `| ${t("line_excise")} | ${pct(cat.excisePct)} | ${usd(b.excise)} |`,
    `| ${t("line_vat")} | ${pct(RATES.vatPct)} | ${usd(b.vat)} |`,
    "",
  ];

  const logistics = [
    `**${t("ccSecLogistics")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColAmount")} |`,
    "|------|------|",
    `| ${t("line_clearance")} | ${usd(b.clearance)} |`,
    `| ${t("line_localTransport")} | ${usd(b.localTransport)} |`,
    "",
  ];

  const resultBlock = [
    `**${t("ccSecResult")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColAmount")} |`,
    "|------|------|",
    `| ${t("ccLandedPort")} | ${usd(b.landedAtPort)} |`,
    `| **${t("ccLandedSite")}** | **${usd(b.landedOnSite)}** |`,
    `| ${t("ccUnitCost")} | ${usd(b.unitCost)} |`,
    "",
  ];

  // 对比表(结论已由顶部 AI 建议给出,此处不再重复 💡 句)
  let compare: string[] = [];
  if (c) {
    compare = [
      `**${t("ccSecCompare")}**`,
      "",
      `| ${t("ccColItem")} | ${t("ccImport")} | ${t("ccLocal")} |`,
      "|------|------|------|",
      `| ${t("ccUnitCost")} | ${usd(c.importUnit)} | ${usd(c.localUnit)} |`,
      `| ${t("ccLandedSite")} | ${usd(c.importOnSite)} | ${usd(c.localOnSite)} |`,
      "",
    ];
  }

  // 各司其职:
  // - 比价模式(compare)= 只出对比结论(货物上下文 + 进口 vs 本地对比表),不展开进口税费/物流明细。
  // - 成本模式(cost)  = 完整进口到岸/到场拆解,对比作为可选附录。
  // 比价模式的货物信息只保留用户输入的三项(品类/数量/目的城市),不展示内置的体积/重量。
  const goodsLite = [
    `**${t("ccSecGoods")}**`,
    "",
    `| ${t("ccColItem")} | ${t("ccColValue")} |`,
    "|------|------|",
    `| ${t("ccCategory")} | ${t("cat_" + cat.id)}（HS ${cat.hsCode}） |`,
    `| ${t("ccQuantity")} | ${input.quantity} ${t("ccPcs")} |`,
    `| ${t("ccDestCity")} | ${t("city_" + input.destCity)} |`,
    "",
  ];

  const detail = [...goods, ...price, ...tax, ...logistics];
  const blocks = compareMode
    ? [...goodsLite, ...compare]
    : [...detail, ...resultBlock, ...compare];

  blocks.push(`_${t("ccDisclaimer")}_`);
  return blocks.join("\n");
}

// ─── 流式"思考"过程 ──────────────────────────────
function ThinkingView({
  steps,
  current,
  t,
}: {
  steps: string[];
  current: number;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  return (
    <div className="mx-auto max-w-xl">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Sparkles className="h-4 w-4 animate-pulse text-teal-600" />
        {t("aiThinking")}
      </div>
      <div className="mt-4 space-y-2.5">
        {steps.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div
              key={s}
              className={
                "flex items-center gap-2.5 text-sm transition-colors " +
                (done ? "text-teal-700" : active ? "text-ink" : "text-slate-300")
              }
            >
              <span className="flex h-5 w-5 items-center justify-center">
                {done ? (
                  <Check className="h-4 w-4" />
                ) : active ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                )}
              </span>
              {t(s)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── 打字机 ──────────────────────────────────────
function useTypewriter(text: string, speed = 18): string {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    if (!text) return;
    const iv = setInterval(() => {
      setN((x) => {
        if (x >= text.length) {
          clearInterval(iv);
          return x;
        }
        return x + 1;
      });
    }, speed);
    return () => clearInterval(iv);
  }, [text, speed]);
  return text.slice(0, n);
}

// ─── AI 结论/建议(规则驱动的自然语言) ────────────
function buildConclusion(
  result: Result,
  t: (key: string, values?: Record<string, string | number>) => string,
  compareMode: boolean,
): string {
  const { breakdown: b, comparison: c, input } = result;
  const catName = t(`cat_${b.category.id}`);
  if (compareMode && c) {
    const values = {
      cat: catName,
      pct: Math.abs(c.deltaPct).toFixed(1),
      save: usd(Math.abs(c.importUnit - c.localUnit)),
    };
    return c.cheaper === "local" ? t("aiConclLocal", values) : t("aiConclImport", values);
  }
  return t("aiConclCost", {
    qty: input.quantity,
    cat: catName,
    city: t(`city_${input.destCity}`),
    total: usd(b.landedOnSite),
    unit: usd(b.unitCost),
  });
}

// ─── 小组件 ──────────────────────────────────────
function usd(n: number): string {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      {children}
    </label>
  );
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm focus:border-teal-400 focus:outline-none"
    >
      {children}
    </select>
  );
}

function NumInput({
  value,
  onChange,
  suffix,
}: {
  value: string;
  onChange: (v: string) => void;
  suffix?: string;
}) {
  return (
    <div className="flex items-center rounded-xl border border-slate-200 bg-white focus-within:border-teal-400">
      <input
        type="number"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl bg-transparent px-3 py-2.5 text-sm focus:outline-none"
      />
      {suffix && <span className="pr-3 text-xs text-slate-400">{suffix}</span>}
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        "rounded-2xl border px-3 py-3 text-center " +
        (highlight ? "border-teal-300 bg-teal-50" : "border-slate-200 bg-white")
      }
    >
      <div className="text-[11px] text-ink-2">{label}</div>
      <div className={"mt-1 text-sm font-black " + (highlight ? "text-teal-700" : "text-ink")}>
        {value}
      </div>
    </div>
  );
}
