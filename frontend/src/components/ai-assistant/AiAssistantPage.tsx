"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Bot, ChevronLeft, Sparkles, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { AGENTS, matchAnswer, getGreeting, getSuggestions, type AgentDef } from "./mockAgentData";

// ─── 类型 ────────────────────────────────────────
interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
}

// ─── Agent 卡片 meta — 用 i18n key 映射 ─────────
interface AgentMeta {
  titleKey: string;
  subtitleKey: string;
  featureKeys: string[];
  btnGradient: string;
  tagBg: string;
  tagText: string;
  tagBorder: string;
}

const AGENT_META: Record<string, AgentMeta> = {
  container: {
    titleKey: "containerTitle",
    subtitleKey: "containerSubtitle",
    featureKeys: ["containerTag1", "containerTag2", "containerTag3"],
    btnGradient: "linear-gradient(120deg, #003f46, #006773)",
    tagBg: "bg-teal-50", tagText: "text-teal-800", tagBorder: "border-teal-200",
  },
  compliance: {
    titleKey: "complianceTitle",
    subtitleKey: "complianceSubtitle",
    featureKeys: ["complianceTag1", "complianceTag2", "complianceTag3"],
    btnGradient: "linear-gradient(120deg, #c1850b, #e3a615)",
    tagBg: "bg-[#fdf4dc]", tagText: "text-[#92680a]", tagBorder: "border-[#f0d97a]",
  },
  procurement: {
    titleKey: "procurementTitle",
    subtitleKey: "procurementSubtitle",
    featureKeys: ["procurementTag1", "procurementTag2", "procurementTag3"],
    btnGradient: "linear-gradient(120deg, #003f46, #006773)",
    tagBg: "bg-teal-50", tagText: "text-teal-800", tagBorder: "border-teal-200",
  },
  finder: {
    titleKey: "finderTitle",
    subtitleKey: "finderSubtitle",
    featureKeys: ["finderTag1", "finderTag2", "finderTag3"],
    btnGradient: "linear-gradient(120deg, #c1850b, #e3a615)",
    tagBg: "bg-[#fdf4dc]", tagText: "text-[#92680a]", tagBorder: "border-[#f0d97a]",
  },
};

// ─── 主页面 ──────────────────────────────────────
export function AiAssistantPage() {
  const t = useTranslations("aiAssistant");
  const [activeAgent, setActiveAgent] = useState<AgentDef | null>(null);

  return (
    <div>
      {/* Hero */}
      <div className="rounded-2xl bg-gradient-to-r from-[#00505a] to-[#003a40] px-4 sm:px-6 mb-6 min-h-[160px] sm:min-h-[190px] flex items-center justify-center py-6">
        <div className="flex flex-col items-center text-center">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1 text-sm text-white/80">
            <Sparkles className="h-4 w-4" />
            AI-Powered
          </div>
          <h1 className="text-lg sm:text-xl md:text-2xl font-bold text-white mb-1">
            {t("heroTitle")}
          </h1>
          <p className="text-[12px] sm:text-[13px] text-white/65 leading-snug sm:whitespace-nowrap">
            {t("heroDesc")}
          </p>
          <p className="mt-0.5 text-[11px] sm:text-[12px] text-white/40 sm:whitespace-nowrap">
            {t("heroSubDesc")}
          </p>
        </div>
      </div>

      {/* Agent 卡片 */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {AGENTS.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onStart={() => setActiveAgent(agent)}
          />
        ))}
      </div>

      {/* 底部说明 */}
      <div className="text-center pb-4">
        <p className="text-sm text-gray-400">{t("moreComingSoon")}</p>
      </div>

      {/* 对话弹窗 */}
      {activeAgent && (
        <ChatDialog
          agent={activeAgent}
          onClose={() => setActiveAgent(null)}
        />
      )}
    </div>
  );
}

// ─── Agent 卡片 ─────────────────────────────────
function AgentCard({ agent, onStart }: { agent: AgentDef; onStart: () => void }) {
  const t = useTranslations("aiAssistant");
  const meta = AGENT_META[agent.id];

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-white p-5 transition-all hover:shadow-lg hover:-translate-y-1"
      style={{ boxShadow: "0 1px 4px rgba(16,36,65,.05)" }}
    >
      <div className="flex items-start justify-between">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${agent.color} text-xl`}>
          {agent.icon}
        </div>
        <span className={`inline-flex items-center gap-1 rounded-full ${meta.tagBg} px-2 py-0.5 text-[11px] font-medium ${meta.tagText}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          {t("online")}
        </span>
      </div>

      <h3 className="mt-3 text-[15px] font-black text-ink">{t(meta.titleKey)}</h3>
      <p className="mt-1 text-sm text-ink-2 leading-relaxed">{t(meta.subtitleKey)}</p>

      <div className="mt-3 flex flex-wrap gap-1.5 flex-1 content-start">
        {meta.featureKeys.map((k) => (
          <span
            key={k}
            className={`rounded-full border ${meta.tagBorder} ${meta.tagBg} px-2.5 py-1 text-xs ${meta.tagText}`}
          >
            {t(k)}
          </span>
        ))}
      </div>

      <button
        onClick={onStart}
        className="mt-4 w-full rounded-xl py-2.5 text-sm font-bold text-white transition-all hover:opacity-90"
        style={{ background: meta.btnGradient }}
      >
        {t("startChat")}
      </button>
    </div>
  );
}

// ─── 对话弹窗 ────────────────────────────────────
function ChatDialog({ agent, onClose }: { agent: AgentDef; onClose: () => void }) {
  const t = useTranslations("aiAssistant");
  const locale = useLocale();
  const meta = AGENT_META[agent.id];
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const seqRef = useRef(0);

  useEffect(() => {
    setMessages([
      { id: ++seqRef.current, role: "assistant", content: getGreeting(agent, locale) },
    ]);
  }, [agent, locale]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, streamedContent]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const typeAnswer = useCallback((answer: string) => {
    setStreaming(true);
    setStreamedContent("");
    let idx = 0;
    const timer = setInterval(() => {
      idx++;
      setStreamedContent(answer.slice(0, idx));
      if (idx >= answer.length) {
        clearInterval(timer);
        setMessages((m) => [
          ...m,
          { id: ++seqRef.current, role: "assistant", content: answer },
        ]);
        setStreamedContent("");
        setStreaming(false);
      }
    }, 15);
  }, []);

  function handleSend(text?: string) {
    const userText = (text ?? input).trim();
    if (!userText || streaming) return;
    setInput("");
    setShowSuggestions(false);
    setMessages((m) => [
      ...m,
      { id: ++seqRef.current, role: "user", content: userText },
    ]);
    setTimeout(() => {
      const answer = matchAnswer(agent, userText, locale);
      typeAnswer(answer);
    }, 300);
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm sm:p-4">
      <div className="flex h-[92vh] sm:h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl bg-white shadow-2xl">
        {/* 顶栏 */}
        <div
          className="flex items-center gap-3 px-4 sm:px-5 py-3.5 text-white"
          style={{ background: "linear-gradient(120deg, #003f46, #00505a 60%, #006773)" }}
        >
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/15 hover:bg-white/25 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 text-lg">
            {agent.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold truncate">{t(meta.titleKey)}</div>
            <div className="text-xs text-white/60">{t("dialogOnline")}</div>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/15 hover:bg-white/25 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 消息区 */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-3 sm:px-4 py-5 space-y-4 bg-[#f7f7f8]"
        >
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {streaming && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white shadow-sm text-sm">
                <Bot className="h-4 w-4 text-teal-700" />
              </div>
              <div className="max-w-[85%] rounded-2xl rounded-tl-md bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm">
                {streamedContent ? (
                  <MarkdownLite text={streamedContent} />
                ) : (
                  <span className="inline-flex items-center gap-1 text-slate-400">
                    <span className="animate-bounce" style={{ animationDelay: "0ms" }}>·</span>
                    <span className="animate-bounce" style={{ animationDelay: "150ms" }}>·</span>
                    <span className="animate-bounce" style={{ animationDelay: "300ms" }}>·</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {showSuggestions && !streaming && messages.length <= 1 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {getSuggestions(agent, locale).map((s) => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="rounded-xl border border-line bg-white px-3 sm:px-4 py-2 text-sm text-ink-2 shadow-sm transition-all hover:border-teal-300 hover:bg-teal-50/50 hover:text-teal-800 hover:shadow"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 输入区 */}
        <ChatInputBar
          value={input}
          onChange={setInput}
          onSend={() => handleSend()}
          streaming={streaming}
          t={t}
        />
      </div>
    </div>
  );
}

// ─── 消息气泡 ──────────────────────────────────
function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[85%] rounded-2xl rounded-tr-md px-4 py-3 text-sm leading-relaxed text-white"
          style={{ background: "linear-gradient(120deg, #003f46, #006773)" }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white shadow-sm text-sm">
        <Bot className="h-4 w-4 text-teal-700" />
      </div>
      <div className="max-w-[85%] rounded-2xl rounded-tl-md bg-white px-4 py-3 text-sm leading-relaxed text-slate-800 shadow-sm">
        <MarkdownLite text={message.content} />
      </div>
    </div>
  );
}

// ─── 输入框 ──────────────────────────────────────
function ChatInputBar({
  value,
  onChange,
  onSend,
  streaming,
  t,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  streaming: boolean;
  t: (key: string) => string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 8 * 24)}px`;
  }, [value]);

  const canSend = !streaming && !!value.trim();

  return (
    <div className="border-t border-slate-100 bg-white px-3 sm:px-4 py-3">
      <div
        className={
          "relative flex items-end gap-2 rounded-2xl border bg-slate-50 transition-colors " +
          (canSend
            ? "border-slate-300 focus-within:border-slate-400"
            : "border-slate-200 focus-within:border-slate-300")
        }
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
          disabled={streaming}
          placeholder={streaming ? t("inputStreaming") : t("inputPlaceholder")}
          rows={1}
          className="flex-1 resize-none bg-transparent px-4 py-3 text-sm leading-6 text-slate-800 placeholder:text-slate-400 focus:outline-none disabled:text-slate-400"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          className={
            "mb-2.5 mr-2.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all " +
            (canSend
              ? "text-white shadow-sm hover:opacity-90"
              : "bg-slate-200 text-slate-400")
          }
          style={canSend ? { background: "linear-gradient(120deg, #003f46, #006773)" } : undefined}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-1.5 flex items-center justify-between px-1">
        <span className="text-[10px] text-slate-400">{t("inputHintSend")}</span>
        <span className="text-[10px] text-slate-400">{t("poweredBy")}</span>
      </div>
    </div>
  );
}

// ─── 简易 Markdown 渲染 ────────────────────────
function MarkdownLite({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      elements.push(
        <pre
          key={`code-${i}`}
          className="my-2 overflow-x-auto rounded-lg bg-slate-800 px-3 py-2 text-xs leading-5 text-slate-200"
        >
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    if (line.trimStart().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      elements.push(<MdTable key={`tbl-${i}`} rows={tableLines} />);
      continue;
    }

    elements.push(
      <p key={`p-${i}`} className="min-h-[1.25em]">
        <InlineFormat text={line} />
      </p>,
    );
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
}

function InlineFormat({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, idx) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={idx} className="font-semibold text-slate-900">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={idx}>{p}</span>
        ),
      )}
    </>
  );
}

function MdTable({ rows }: { rows: string[] }) {
  const parse = (row: string) =>
    row.split("|").map((c) => c.trim()).filter(Boolean);

  const hasHeader =
    rows.length >= 2 && parse(rows[1]).every((c) => /^[-:]+$/.test(c));

  const headerCells = hasHeader ? parse(rows[0]) : null;
  const bodyRows = hasHeader ? rows.slice(2) : rows;

  return (
    <div className="my-2 overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-xs">
        {headerCells && (
          <thead>
            <tr className="bg-slate-100">
              {headerCells.map((c, i) => (
                <th key={i} className="whitespace-nowrap px-3 py-1.5 text-left font-semibold text-slate-700">
                  <InlineFormat text={c} />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {bodyRows.map((row, ri) => {
            const cells = parse(row);
            if (cells.length === 0) return null;
            return (
              <tr key={ri} className="border-t border-slate-100">
                {cells.map((c, ci) => (
                  <td key={ci} className="whitespace-nowrap px-3 py-1.5 text-slate-600">
                    <InlineFormat text={c} />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
