"use client";

import { CopyIcon, InfoIcon, Loader2Icon, PlayIcon, TerminalIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchPolicies, useAsync } from "@/lib/data";
import { normaliseReport } from "@/lib/scoring";
import { saveUploadedReport } from "@/lib/store";
import type { AuditMode } from "@/lib/types";
import { cn } from "@/lib/utils";

const FALLBACK_POLICIES = [
  { id: "eu-ai-act", name: "EU AI Act" },
  { id: "gdpr", name: "GDPR" },
  { id: "internal-ai-policy", name: "Internal AI policy" },
];

const MODES: { value: AuditMode; title: string; desc: string }[] = [
  { value: "deterministic", title: "Deterministic", desc: "YAML / Rego rules only. Fast, reproducible, no LLM." },
  { value: "hybrid", title: "Hybrid", desc: "Rules first, LLM judge for ambiguous requirements, Verifier checks citations." },
  { value: "llm", title: "LLM", desc: "LLM judge on retrieved evidence for every requirement." },
];

const GH_URL = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+?(\.git)?\/?$/;

export function AuditForm({ apiUrl }: { apiUrl: string }) {
  const router = useRouter();
  const { data: policies } = useAsync(() => fetchPolicies().catch(() => null), ["policies"]);
  const options = policies?.length ? policies.map((p) => ({ id: p.id, name: p.name })) : FALLBACK_POLICIES;

  const [repo, setRepo] = useState("");
  const [selected, setSelected] = useState<string[]>(["eu-ai-act", "gdpr"]);
  const [mode, setMode] = useState<AuditMode>("hybrid");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const repoOk = GH_URL.test(repo.trim());
  const policyIds = selected.filter((s) => options.some((o) => o.id === s));
  const cmdTarget = repo.trim() ? `./${repo.trim().replace(/\/$/, "").split("/").pop()?.replace(/\.git$/, "")}` : "./repo";
  const cli = [
    repo.trim() && repoOk ? `git clone ${repo.trim()} && \\\n  ` : "",
    `ccauditor audit ${cmdTarget} --mode ${mode}`,
    ...policyIds.map((p) => ` --policy ${p}`),
    ` \\\n  --format json --out report.json`,
  ].join("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!repoOk) return setError("Enter a public GitHub repository URL, e.g. https://github.com/org/repo");
    if (!policyIds.length) return setError("Select at least one policy.");
    if (!apiUrl) return;
    setBusy(true);
    try {
      const res = await fetch(`${apiUrl.replace(/\/$/, "")}/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repo.trim(), policies: policyIds, mode }),
      });
      if (!res.ok) throw new Error(`API returned HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`);
      const report = normaliseReport(await res.json());
      saveUploadedReport(report);
      router.push(`/reports/${encodeURIComponent(report.id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <form onSubmit={submit} noValidate className="min-w-0 space-y-7 rounded-xl border bg-card p-5 sm:p-6">
        <div className="space-y-1.5">
          <label htmlFor="repo" className="text-sm font-medium">
            GitHub repository URL
          </label>
          <Input
            id="repo"
            type="url"
            inputMode="url"
            placeholder="https://github.com/org/repo"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            aria-invalid={repo.length > 0 && !repoOk}
            aria-describedby="repo-hint"
            className="font-mono"
          />
          <p id="repo-hint" className="text-xs text-muted-foreground">
            Public repositories only. The repository is cloned read-only for the duration of the audit.
          </p>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Policies</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {options.map((p) => {
              const on = selected.includes(p.id);
              return (
                <label
                  key={p.id}
                  className={cn(
                    "flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors hover:bg-muted/50",
                    on && "border-primary/60 bg-accent/40",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => setSelected(on ? selected.filter((s) => s !== p.id) : [...selected, p.id])}
                    className="mt-0.5 size-4 accent-[var(--primary)]"
                  />
                  <span>
                    <span className="block font-medium">{p.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">{p.id}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Evaluation mode</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {MODES.map((m) => (
              <label
                key={m.value}
                className={cn(
                  "flex cursor-pointer flex-col gap-1 rounded-lg border p-3 text-sm transition-colors hover:bg-muted/50",
                  mode === m.value && "border-primary/60 bg-accent/40 ring-1 ring-primary/30",
                )}
              >
                <span className="flex items-center gap-2 font-medium">
                  <input type="radio" name="mode" value={m.value} checked={mode === m.value} onChange={() => setMode(m.value)} className="accent-[var(--primary)]" />
                  {m.title}
                </span>
                <span className="text-xs leading-relaxed text-muted-foreground">{m.desc}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-300">
            {error}
          </p>
        )}

        {apiUrl ? (
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? <Loader2Icon className="animate-spin" /> : <PlayIcon />}
            {busy ? "Auditing... this can take a few minutes" : "Run audit"}
          </Button>
        ) : (
          <div className="flex gap-3 rounded-lg border border-sky-600/30 bg-sky-500/8 p-4 text-sm">
            <InfoIcon className="mt-0.5 size-4 shrink-0 text-sky-700 dark:text-sky-400" aria-hidden />
            <div className="space-y-1.5">
              <p className="font-medium">No audit API is configured for this deployment.</p>
              <p className="text-muted-foreground">
                LLM-based audits run locally through the CLI, which drives Claude Code in headless mode with your own
                subscription (no API key). Run the command on the right, then upload the resulting JSON on the{" "}
                <Link href="/reports" className="font-medium text-foreground underline">
                  Reports
                </Link>{" "}
                page. Set <code className="font-mono text-xs">NEXT_PUBLIC_API_URL</code> to enable this form.
              </p>
            </div>
          </div>
        )}
      </form>

      <aside className="min-w-0 space-y-4">
        <div className="overflow-hidden rounded-xl border bg-zinc-950 text-zinc-100 dark:bg-black">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-zinc-400">
            <span className="flex items-center gap-1.5">
              <TerminalIcon className="size-3.5" aria-hidden /> Equivalent CLI
            </span>
            <button
              type="button"
              className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-white/10 hover:text-zinc-100"
              onClick={() => {
                navigator.clipboard?.writeText(cli.replace(/\\\n\s*/g, "")).then(() => {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                });
              }}
            >
              <CopyIcon className="size-3" aria-hidden /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed">
            <span className="text-zinc-500 select-none">$ </span>
            {cli}
          </pre>
        </div>
        <ol className="space-y-3 rounded-xl border bg-card p-4 text-sm">
          {[
            ["Install", "pip install -e app/backend (Python 3.11+). Claude Code CLI must be logged in for llm/hybrid modes."],
            ["Audit", "The CLI writes a JSON report (plus Markdown and SARIF) for the target repository."],
            ["Review", "Upload the JSON here, resolve the review queue, export reviews and apply them with ccauditor review apply."],
          ].map(([t, d], i) => (
            <li key={t} className="flex gap-3">
              <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-xs text-primary-foreground">
                {i + 1}
              </span>
              <span>
                <span className="font-medium">{t}. </span>
                <span className="text-muted-foreground">{d}</span>
              </span>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
