"use client";

import { ExternalLinkIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useState } from "react";
import { SeverityLabel } from "@/components/badges";
import { Input } from "@/components/ui/input";
import { fetchPolicies, useAsync } from "@/lib/data";
import { CATEGORY_LABEL, label } from "@/lib/meta";
import type { PolicyWithRequirements } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_LABEL: Record<string, string> = {
  regulation: "Regulation",
  internal_policy: "Internal policy",
  control_framework: "Control framework",
};

export function PolicyBrowser() {
  const { data, error, loading } = useAsync(fetchPolicies, ["policies"]);
  const [active, setActive] = useState<string | null>(null);
  const [q, setQ] = useState("");

  if (loading)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2Icon className="size-4 animate-spin" aria-hidden /> Loading policies...
      </p>
    );
  if (error || !data) return <p className="text-sm text-red-600">Could not load policies/index.json: {error}</p>;
  if (!data.length) return <p className="text-sm text-muted-foreground">No policies published.</p>;

  const current = data.find((p) => p.id === active) ?? data[0];

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <nav aria-label="Policies" className="space-y-2 lg:sticky lg:top-20 lg:self-start">
        {data.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setActive(p.id)}
            aria-current={p.id === current.id ? "true" : undefined}
            className={cn(
              "w-full rounded-lg border bg-card p-3 text-left transition-colors hover:bg-muted/50",
              p.id === current.id && "border-primary/60 ring-1 ring-primary/30",
            )}
          >
            <span className="block font-mono text-xs text-muted-foreground">{p.id}</span>
            <span className="mt-0.5 block text-sm leading-snug font-medium">{p.name}</span>
            <span className="mt-2 flex gap-3 text-xs text-muted-foreground">
              <span>{p.requirements?.length ?? 0} requirements</span>
              <span>{p.clauses?.length ?? 0} clauses</span>
            </span>
          </button>
        ))}
      </nav>
      <PolicyDetail policy={current} q={q} setQ={setQ} />
    </div>
  );
}

function PolicyDetail({ policy, q, setQ }: { policy: PolicyWithRequirements; q: string; setQ: (s: string) => void }) {
  const clauses = new Map((policy.clauses ?? []).map((c) => [c.id, c]));
  const needle = q.trim().toLowerCase();
  const reqs = (policy.requirements ?? []).filter(
    (r) => !needle || [r.id, r.title, r.statement, r.category, ...r.clause_ids].join(" ").toLowerCase().includes(needle),
  );

  return (
    <section className="min-w-0 space-y-5">
      <div className="rounded-xl border bg-card p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded bg-muted px-1.5 py-0.5 font-mono">{policy.id}</span>
          {policy.kind && <span className="rounded border px-1.5 py-0.5">{KIND_LABEL[policy.kind] ?? policy.kind}</span>}
          {policy.version && <span className="text-muted-foreground">version {policy.version}</span>}
        </div>
        <h2 className="mt-2 font-heading text-2xl font-semibold">{policy.name}</h2>
        {policy.source && (
          <p className="mt-1 text-sm break-all text-muted-foreground">
            Source:{" "}
            {/^https?:\/\//.test(policy.source) ? (
              <a href={policy.source} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline">
                {policy.source} <ExternalLinkIcon className="size-3" aria-hidden />
              </a>
            ) : (
              <code className="font-mono text-xs">{policy.source}</code>
            )}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-heading text-lg font-semibold">Requirements</h3>
        <label className="relative w-full sm:w-72">
          <span className="sr-only">Search requirements</span>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter requirements..." className="pl-8" />
        </label>
      </div>

      <ul className="space-y-3">
        {reqs.map((r) => (
          <li key={r.id} className="rounded-xl border bg-card p-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-mono text-xs font-semibold text-primary">{r.id}</span>
              <span className="text-xs text-muted-foreground">{label(CATEGORY_LABEL, r.category)}</span>
              <SeverityLabel severity={r.severity} />
              <span className="ml-auto flex gap-1">
                {r.applies_to?.map((a) => (
                  <span key={a} className="rounded bg-muted px-1.5 py-px font-mono text-[10px] text-muted-foreground uppercase">
                    {a}
                  </span>
                ))}
              </span>
            </div>
            <p className="mt-1.5 font-medium">{r.title}</p>
            <p className="mt-1 font-heading text-[15px] leading-relaxed text-pretty text-muted-foreground">{r.statement}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {r.clause_ids.map((cid) => (
                <span
                  key={cid}
                  title={clauses.get(cid)?.text}
                  className="rounded border-l-2 border-primary/50 bg-muted/60 px-2 py-0.5 font-mono text-[11px]"
                >
                  {cid}
                  {clauses.get(cid)?.title && <span className="font-sans text-muted-foreground"> · {clauses.get(cid)?.title}</span>}
                </span>
              ))}
            </div>
            {(r.checks?.length ?? 0) > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Deterministic checks: {r.checks.map((c) => c.description || c.type).join("; ")}
              </p>
            )}
          </li>
        ))}
        {reqs.length === 0 && <li className="py-8 text-center text-sm text-muted-foreground">No requirements match.</li>}
      </ul>

      {(policy.clauses?.length ?? 0) > 0 && (
        <details className="rounded-xl border bg-card p-4">
          <summary className="cursor-pointer font-heading text-lg font-semibold">Clauses ({policy.clauses!.length})</summary>
          <dl className="mt-3 divide-y">
            {policy.clauses!.map((c) => (
              <div key={c.id} className="py-2.5">
                <dt className="font-mono text-xs font-medium">
                  {c.id} {c.title && <span className="font-sans text-muted-foreground">· {c.title}</span>}
                </dt>
                <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">{c.text}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
