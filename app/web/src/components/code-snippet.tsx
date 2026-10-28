import type { ReactNode } from "react";
import { EVIDENCE_KIND_LABEL, label } from "@/lib/meta";
import type { Evidence } from "@/lib/types";

// Very small, dependency-free highlighter: comments, strings, numbers, keywords, YAML/HCL keys.
const KEYWORDS = new Set(
  (
    "def class return if elif else for while in not and or is None True False import from as with try except raise " +
    "lambda yield async await pass const let var function export default new this null undefined true false type interface " +
    "extends implements public private resource module variable provider data locals output"
  ).split(" "),
);

const TOKEN = /(#[^\n]*|\/\/[^\n]*|<!--.*?-->)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w-]*)(?=\s*:(?!:))|([A-Za-z_]\w*)/g;

function highlightLine(line: string, lang: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  const isProse = lang === "md" || lang === "txt" || lang === "mdx";
  if (isProse) return [line];
  for (const m of line.matchAll(TOKEN)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push(line.slice(last, idx));
    const [tok, com, str, num, key, word] = m;
    let cls = "";
    if (com) cls = "tok-com";
    else if (str) cls = "tok-str";
    else if (num) cls = "tok-num";
    else if (key && (lang === "yaml" || lang === "yml" || lang === "json")) cls = "tok-key";
    else if ((word || key) && KEYWORDS.has(word ?? key)) cls = "tok-kw";
    out.push(cls ? <span key={i++} className={cls}>{tok}</span> : tok);
    last = idx + tok.length;
  }
  if (last < line.length) out.push(line.slice(last));
  return out;
}

export function CodeSnippet({ evidence, maxLines = 40 }: { evidence: Evidence; maxLines?: number }) {
  const ext = evidence.path.split(".").pop()?.toLowerCase() ?? "";
  const lines = evidence.snippet.replace(/\n$/, "").split("\n");
  const shown = lines.slice(0, maxLines);
  const width = String(evidence.start_line + shown.length).length;

  return (
    <figure className="overflow-hidden rounded-lg border bg-card">
      <figcaption className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-muted/60 px-3 py-1.5 font-mono text-xs">
        <span className="font-medium break-all text-foreground">
          {evidence.path}
          <span className="text-muted-foreground">
            :L{evidence.start_line}-L{evidence.end_line}
          </span>
        </span>
        <span className="ml-auto flex items-center gap-2 text-muted-foreground">
          <span className="rounded bg-background px-1.5 py-px ring-1 ring-border">
            {label(EVIDENCE_KIND_LABEL, evidence.kind)}
          </span>
          {evidence.signal && <span title="Collector signal">{evidence.signal}</span>}
          <span className="tabular" title="Retrieval score">
            {evidence.score.toFixed(2)}
          </span>
        </span>
      </figcaption>
      <pre className="max-h-96 overflow-auto py-2 text-[12.5px] leading-[1.6]">
        <code className="grid font-mono">
          {shown.map((l, i) => (
            <span key={i} className="flex px-3 hover:bg-muted/50">
              <span
                aria-hidden
                className="mr-4 inline-block shrink-0 text-right text-muted-foreground/60 select-none"
                style={{ width: `${width}ch` }}
              >
                {evidence.start_line + i}
              </span>
              <span className="whitespace-pre">{highlightLine(l, ext)}</span>
            </span>
          ))}
          {lines.length > shown.length && (
            <span className="px-3 text-muted-foreground">... {lines.length - shown.length} more lines</span>
          )}
        </code>
      </pre>
    </figure>
  );
}
