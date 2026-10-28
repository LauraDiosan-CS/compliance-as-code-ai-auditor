"use client";

import { AlertTriangleIcon, ChevronRightIcon, WrenchIcon } from "lucide-react";
import { MethodTag, SeverityLabel, StatusBadge, VerifiedTag } from "@/components/badges";
import { CodeSnippet } from "@/components/code-snippet";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { CATEGORY_LABEL, STATUS_META, label } from "@/lib/meta";
import type { ReportModel } from "@/lib/report-model";
import type { StoredReview } from "@/lib/types";
import { ReviewPanel } from "./review-form";

function Section({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function RequirementSheet({
  model,
  reqId,
  onClose,
  onSave,
  onRemove,
}: {
  model: ReportModel;
  reqId: string | null;
  onClose: () => void;
  onSave: (r: StoredReview) => void;
  onRemove: (id: string) => void;
}) {
  const row = reqId ? model.rowById.get(reqId) : undefined;
  const v = row?.verdict;

  return (
    <Sheet open={!!row} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        {row && (
          <>
            <SheetHeader className="border-b pr-12">
              <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{row.req.id}</span>
                <ChevronRightIcon className="size-3" aria-hidden />
                <span>{row.req.policy_id}</span>
                <span aria-hidden>·</span>
                <span>{label(CATEGORY_LABEL, row.req.category)}</span>
              </div>
              <SheetTitle className="font-heading text-xl leading-snug font-semibold">{row.req.title}</SheetTitle>
              <SheetDescription className="sr-only">Requirement detail, verdict, evidence and human review.</SheetDescription>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <StatusBadge status={v?.status} />
                {v && <MethodTag method={v.method} />}
                <SeverityLabel severity={row.req.severity} />
                {v && <VerifiedTag verified={v.verified} resolved={row.evidence.length} total={v.evidence_ids.length} />}
              </div>
            </SheetHeader>

            <div className="space-y-6 p-4 sm:p-5">
              <Section title="Requirement statement">
                <p className="font-heading text-[15px] leading-relaxed text-pretty">{row.req.statement}</p>
              </Section>

              <Section title="Source clauses">
                <ul className="space-y-2">
                  {row.req.clause_ids.map((cid) => {
                    const c = model.clauses.get(cid);
                    return (
                      <li key={cid} className="rounded-md border-l-2 border-primary/40 bg-muted/40 py-1.5 pr-2 pl-3 text-sm">
                        <span className="font-mono text-xs font-medium">{cid}</span>
                        {c?.title && <span className="text-muted-foreground"> · {c.title}</span>}
                        {c?.text && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{c.text}</p>}
                      </li>
                    );
                  })}
                </ul>
              </Section>

              {v ? (
                <>
                  <Section
                    title="Verdict"
                    aside={
                      <span className="flex items-center gap-2 text-xs text-muted-foreground">
                        Confidence
                        <span className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
                          <span
                            className="block h-full rounded-full"
                            style={{ width: `${v.confidence * 100}%`, background: STATUS_META[v.status].color }}
                          />
                        </span>
                        <span className="tabular font-mono">{Math.round(v.confidence * 100)}%</span>
                      </span>
                    }
                  >
                    {row.review && row.original && row.original.status !== v.status && (
                      <p className="text-xs text-muted-foreground">
                        Pipeline verdict: <StatusBadge status={row.original.status} /> via {row.original.method}
                      </p>
                    )}
                    <p className="text-sm leading-relaxed text-pretty">{row.original?.rationale || v.rationale || "No rationale provided."}</p>
                  </Section>

                  {v.gaps.length > 0 && (
                    <Section title={`Gaps (${v.gaps.length})`}>
                      <ul className="space-y-1.5">
                        {v.gaps.map((g) => (
                          <li key={g} className="flex gap-2 text-sm">
                            <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" aria-hidden />
                            {g}
                          </li>
                        ))}
                      </ul>
                    </Section>
                  )}

                  {v.remediation && (
                    <Section title="Remediation">
                      <div className="flex gap-2 rounded-lg bg-emerald-500/8 p-3 text-sm ring-1 ring-emerald-600/20 ring-inset">
                        <WrenchIcon className="mt-0.5 size-4 shrink-0 text-emerald-700 dark:text-emerald-400" aria-hidden />
                        <p className="leading-relaxed text-pretty">{v.remediation}</p>
                      </div>
                    </Section>
                  )}

                  <Section title={`Cited evidence (${row.evidence.length})`}>
                    {row.evidence.length === 0 && row.missingCitations.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No evidence cited. {v.status === "non_compliant" ? "The requirement is unmet: no supporting artefact was found." : ""}
                      </p>
                    )}
                    {row.missingCitations.length > 0 && (
                      <p className="rounded-md bg-red-500/10 px-3 py-2 text-xs text-red-800 dark:text-red-300">
                        {row.missingCitations.length} cited evidence id(s) not found in the report: {row.missingCitations.join(", ")}
                      </p>
                    )}
                    <div className="space-y-3">
                      {row.evidence.map((e) => (
                        <CodeSnippet key={e.id} evidence={e} />
                      ))}
                    </div>
                  </Section>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No verdict was produced for this requirement.</p>
              )}

              {(row.req.checks.length > 0 || row.req.llm_guidance) && (
                <details className="group rounded-lg border p-3 text-sm">
                  <summary className="cursor-pointer font-medium select-none">How this requirement is checked</summary>
                  <div className="mt-3 space-y-3">
                    {row.req.checks.map((c, i) => (
                      <div key={i} className="rounded-md bg-muted/50 p-2 font-mono text-xs">
                        <div>
                          <span className="font-semibold">{c.type}</span> · expect {c.expect}
                          {c.description && <span className="font-sans text-muted-foreground"> · {c.description}</span>}
                        </div>
                        {c.pattern && <div className="mt-1 break-all text-muted-foreground">/{c.pattern}/</div>}
                        {c.path && <div className="mt-1 text-muted-foreground">path: {c.path}</div>}
                        {c.globs.length > 0 && <div className="mt-1 text-muted-foreground">globs: {c.globs.join(", ")}</div>}
                      </div>
                    ))}
                    {row.req.llm_guidance && (
                      <p className="text-muted-foreground">
                        <span className="font-medium text-foreground">LLM guidance: </span>
                        {row.req.llm_guidance}
                      </p>
                    )}
                  </div>
                </details>
              )}

              <Section title="Human review">
                <ReviewPanel row={row} onSave={onSave} onRemove={onRemove} />
              </Section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
