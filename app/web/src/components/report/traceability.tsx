"use client";

import { ArrowRightIcon, CircleSlashIcon, FileCodeIcon } from "lucide-react";
import { StatusBadge } from "@/components/badges";
import { type ReportModel, rowPriority } from "@/lib/report-model";

/** Requirement -> clauses -> evidence (or gap), grouped by policy. */
export function Traceability({ model, onOpen }: { model: ReportModel; onOpen: (id: string) => void }) {
  const byPolicy = new Map<string, typeof model.rows>();
  for (const r of model.rows) {
    const list = byPolicy.get(r.req.policy_id) ?? [];
    list.push(r);
    byPolicy.set(r.req.policy_id, list);
  }
  const linked = model.rows.filter((r) => r.evidence.length > 0).length;
  const gaps = model.rows.filter((r) => r.evidence.length === 0 && r.verdict?.status !== "not_applicable").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
        <span>
          <strong className="tabular text-foreground">{linked}</strong> requirements linked to evidence
        </span>
        <span>
          <strong className="tabular text-foreground">{gaps}</strong> without evidence (gaps)
        </span>
        <span>
          <strong className="tabular text-foreground">{model.report.evidence.length}</strong> evidence items cited
        </span>
      </div>

      {[...byPolicy.entries()].map(([policy, rows]) => (
        <section key={policy} className="overflow-hidden rounded-xl border bg-card">
          <h3 className="border-b bg-muted/50 px-4 py-2 font-mono text-xs font-semibold tracking-wide">{policy}</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-[11px] tracking-wider text-muted-foreground uppercase">
                <tr className="border-b">
                  <th scope="col" className="w-[30%] px-4 py-2 font-medium">Requirement</th>
                  <th scope="col" className="w-[22%] px-4 py-2 font-medium">Clauses</th>
                  <th scope="col" className="px-4 py-2 font-medium">Evidence / gap</th>
                  <th scope="col" className="w-36 px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].sort((a, b) => a.req.id.localeCompare(b.req.id)).map((r) => (
                  <tr key={r.req.id} className="border-b align-top last:border-0">
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => onOpen(r.req.id)} className="text-left hover:underline">
                        <span className="block font-mono text-xs text-primary">{r.req.id}</span>
                        <span className="font-medium">{r.req.title}</span>
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <ul className="space-y-1">
                        {r.req.clause_ids.map((c) => (
                          <li key={c} className="flex items-center gap-1 font-mono text-xs">
                            <ArrowRightIcon className="size-3 text-muted-foreground" aria-hidden />
                            <span title={model.clauses.get(c)?.title}>{c}</span>
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="px-4 py-3">
                      {r.evidence.length > 0 ? (
                        <ul className="space-y-1">
                          {r.evidence.map((e) => (
                            <li key={e.id} className="flex items-center gap-1.5 font-mono text-xs break-all">
                              <FileCodeIcon className="size-3 shrink-0 text-muted-foreground" aria-hidden />
                              {e.path}
                              <span className="text-muted-foreground">
                                :L{e.start_line}-L{e.end_line}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : r.verdict?.status === "not_applicable" ? (
                        <span className="text-xs text-muted-foreground">Not applicable</span>
                      ) : (
                        <div className="flex gap-1.5 text-xs text-red-700 dark:text-red-400">
                          <CircleSlashIcon className="mt-px size-3.5 shrink-0" aria-hidden />
                          <span>{r.verdict?.gaps[0] ?? "Gap: no supporting evidence found"}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.verdict?.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

export function TopFindings({ model, onOpen }: { model: ReportModel; onOpen: (id: string) => void }) {
  const top = model.rows
    .filter((r) => r.verdict && (r.verdict.status === "non_compliant" || r.verdict.status === "partial"))
    .sort((a, b) => rowPriority(a) - rowPriority(b))
    .slice(0, 5);
  if (!top.length) return <p className="text-sm text-muted-foreground">No open findings.</p>;
  return (
    <ol className="divide-y">
      {top.map((r) => (
        <li key={r.req.id}>
          <button type="button" onClick={() => onOpen(r.req.id)} className="flex w-full items-start gap-3 py-2.5 text-left hover:bg-muted/40">
            <StatusBadge status={r.verdict?.status} className="mt-0.5" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{r.req.title}</span>
              <span className="block truncate text-xs text-muted-foreground">
                <span className="font-mono">{r.req.id}</span> · {r.verdict?.gaps[0] ?? r.verdict?.rationale}
              </span>
            </span>
            <span className="font-mono text-[11px] text-muted-foreground uppercase">{r.req.severity}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
