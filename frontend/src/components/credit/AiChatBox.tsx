"use client";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Bot, Sparkles } from "lucide-react";

import { creditApi, streamAiMessage, type AiMessage } from "@/lib/api/credit";

/** AI 对话框(详情页底部)。
 *
 * 初次进入显示已缓存的 ai_summary,然后用户可追问。每次追问走 SSE 流式接口
 * (POST /credit/ai/conversations/{id}/messages),逐 chunk 渲染。
 */
export function AiChatBox({
  companyId,
  aiSummary,
}: {
  companyId: number;
  aiSummary: string | null;
}) {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 首次挂载创建会话
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const conv = await creditApi.createConversation(companyId);
        if (cancelled) return;
        setConversationId(conv.id);
        setMessages(conv.messages || []);
      } catch (e) {
        if (!cancelled) setError((e as Error).message || "无法创建会话");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  // 滚到底
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streamingContent]);

  async function handleSend() {
    if (!conversationId || !input.trim() || streaming) return;
    const userText = input.trim();
    setInput("");
    setError(null);
    setStreaming(true);
    setStreamingContent("");

    // 本地先 push user 消息(乐观更新)
    const localUserMsg: AiMessage = {
      id: -Date.now(),
      role: "user",
      content: userText,
      sequence: messages.length + 1,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, localUserMsg]);

    let collected = "";
    await streamAiMessage(conversationId, userText, {
      onChunk: (chunk) => {
        collected += chunk;
        setStreamingContent(collected);
      },
      onError: (msg) => {
        setError(msg);
      },
      onDone: () => {
        if (collected) {
          setMessages((m) => [
            ...m,
            {
              id: -Date.now() - 1,
              role: "assistant",
              content: collected,
              sequence: m.length + 1,
              created_at: new Date().toISOString(),
            },
          ]);
        }
        setStreamingContent("");
        setStreaming(false);
      },
    });
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <Sparkles className="h-4 w-4 text-[#FF6B35]" />
        <h3 className="text-sm font-semibold text-slate-900">AI 综合评价</h3>
      </div>

      {/* 顶部:已缓存的 ai_summary */}
      <div className="border-b border-slate-100 px-4 py-3 text-sm leading-relaxed text-slate-700">
        {aiSummary ? (
          <div className="whitespace-pre-wrap">{aiSummary}</div>
        ) : (
          <div className="text-slate-400">
            AI 评价正在生成,或 LLM 暂不可用 — 可直接追问下方对话框。
          </div>
        )}
      </div>

      {/* 对话区 */}
      <div
        ref={scrollRef}
        className="max-h-80 overflow-y-auto px-4 py-3 space-y-3"
      >
        {messages.length === 0 && !streaming && (
          <div className="text-xs text-slate-400">还没有对话,试着问问"主要风险点是什么"。</div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              "flex gap-2 " + (m.role === "user" ? "justify-end" : "justify-start")
            }
          >
            {m.role === "assistant" && (
              <Bot className="mt-1 h-4 w-4 shrink-0 text-[#FF6B35]" />
            )}
            <div
              className={
                "max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm " +
                (m.role === "user"
                  ? "bg-[#003366] text-white"
                  : "bg-slate-50 text-slate-800")
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex gap-2">
            <Bot className="mt-1 h-4 w-4 shrink-0 text-[#FF6B35] animate-pulse" />
            <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-800">
              {streamingContent || <span className="text-slate-400">思考中…</span>}
            </div>
          </div>
        )}
        {error && (
          <div className="text-xs text-red-500">⚠️ {error}</div>
        )}
      </div>

      {/* 输入区 — Claude Code 风格:多行 textarea 自动撑高 + 圆角线框 + 右下 send */}
      <ChatInput
        disabled={!conversationId}
        streaming={streaming}
        value={input}
        onChange={setInput}
        onSend={handleSend}
      />
    </div>
  );
}


/** Claude Code 风格输入框:多行 textarea 自动撑高(2-8 行)+ 右下角 send。 */
function ChatInput({
  disabled,
  streaming,
  value,
  onChange,
  onSend,
}: {
  disabled: boolean;
  streaming: boolean;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 内容变化时自动撑高(2-8 行之间)
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, 8 * 24); // 单行约 24px,封顶 8 行
    el.style.height = `${next}px`;
  }, [value]);

  const canSend = !disabled && !streaming && !!value.trim();

  return (
    <div className="border-t border-slate-100 px-3 py-3">
      <div
        className={
          "relative flex items-end gap-2 rounded-xl border bg-white transition-colors " +
          (canSend
            ? "border-slate-300 focus-within:border-[#003366]"
            : "border-slate-200 focus-within:border-slate-400")
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
          disabled={disabled || streaming}
          placeholder={
            disabled
              ? "正在准备会话…"
              : streaming
                ? "AI 正在回复…"
                : "针对该企业追问任何问题…"
          }
          rows={2}
          className="flex-1 resize-none bg-transparent px-3.5 py-2.5 text-sm leading-6 text-slate-800 placeholder:text-slate-400 focus:outline-none disabled:text-slate-400"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          title="发送(Enter)"
          aria-label="发送"
          className={
            "mb-2 mr-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors " +
            (canSend
              ? "bg-[#003366] text-white hover:bg-[#002244]"
              : "bg-slate-100 text-slate-400")
          }
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-1.5 px-1 text-[10px] text-slate-400">
        Enter 发送 · Shift + Enter 换行
      </div>
    </div>
  );
}
