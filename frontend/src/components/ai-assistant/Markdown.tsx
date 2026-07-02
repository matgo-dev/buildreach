"use client";

import { useLocale } from "next-intl";

/**
 * 简易 Markdown 渲染 — 支持:代码块 ```、表格 |、粗体 **、站内/外链接 [label](url)。
 * AI 助手对话与成本测算结果共用。
 */
export function MarkdownLite({ text }: { text: string }) {
  const locale = useLocale();
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
      elements.push(<MdTable key={`tbl-${i}`} rows={tableLines} locale={locale} />);
      continue;
    }

    elements.push(
      <p key={`p-${i}`} className="min-h-[1.25em]">
        <InlineFormat text={line} locale={locale} />
      </p>,
    );
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
}

export function InlineFormat({ text, locale }: { text: string; locale: string }) {
  // 先拆链接 [label](url)，再拆粗体 **text**
  const parts = text.split(/(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, idx) => {
        const linkMatch = p.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (linkMatch) {
          const [, label, url] = linkMatch;
          // 站内链接自动拼 locale 前缀
          const href = url.startsWith("/") ? `/${locale}${url}` : url;
          return (
            <a key={idx} href={href} target="_blank" rel="noopener noreferrer" className="text-teal-600 underline hover:text-teal-800">
              {label}
            </a>
          );
        }
        if (p.startsWith("**") && p.endsWith("**")) {
          return (
            <strong key={idx} className="font-semibold text-slate-900">
              {p.slice(2, -2)}
            </strong>
          );
        }
        return <span key={idx}>{p}</span>;
      })}
    </>
  );
}

export function MdTable({ rows, locale }: { rows: string[]; locale: string }) {
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
                  <InlineFormat text={c} locale={locale} />
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
                    <InlineFormat text={c} locale={locale} />
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
