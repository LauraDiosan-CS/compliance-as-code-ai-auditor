"use client";

import { CheckCircle2Icon, DownloadIcon, InboxIcon, Trash2Icon } from "lucide-react";
import { SeverityLabel, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { fmtDate } from "@/lib/meta";
import { type ReportModel, rowPriority } from "@/lib/report-model";
import { downloadJson, toReviewExport } from "@/lib/store";
import type { StoredReview } from "@/lib/types";

export function ReviewQueue({
  model,
  reviews,
  onOpen,
  onClear,
}: {
  model: ReportModel;
  reviews: Record<string, StoredReview>;
  onOpen: (id: string) => void;
  onClear: () => void;
}) {
  const pending = model.rows
    .filter((r) => !r.review && (r.original?.status ?? "needs_review") === "needs_review")
    .sort((a, b) => rowPriority(a) - rowPriority(b));
  const reviewed = model.rows.filter((r) => r.review);
  const exportData = toReviewExport(reviews);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section className="space-y-3">
        <h3 className="flex items-center gap-2 font-heading text-lg font-semibold">
          Pending review
          <span className="tabular rounded-full bg-violet-500/15 px-2 font-mono text-xs text-violet-800 dark:text-violet-300">{pending.length}</span>
        </h3>
        <p className="text-sm text-muted-foreground">
          Verdicts the pipeline marked <StatusBadge status="needs_review" /> because of low confidence or conflicting
          signals. Each needs a human decision with a justification. Any other verdict can also be reviewed from its detail panel.
        </p>
        {pending.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center text-sm text-muted-foreground">
            <CheckCircle2Icon className="size-6 text-emerald-600" aria-hidden />
            Queue is empty. All borderline verdicts have been reviewed.
          </div>
        ) : (
          <ul className="space-y-2">
            {pending.map((r) => (
              <li key={r.req.id} className="rounded-xl border bg-card p-4">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{r.req.id}</span>
                      <SeverityLabel severity={r.req.severity} />
                      {r.original && (
                        <span className="tabular font-mono text-xs text-muted-foreground">conf. {Math.round(r.original.confidence * 100)}%</span>
                      )}
                    </div>
                    <p className="mt-1 font-medium">{r.req.title}</p>
                    <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{r.original?.rationale}</p>
                  </div>
                  <Button size="sm" onClick={() => onOpen(r.req.id)}>
                    Review
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <aside className="space-y-3">
        <div className="rounded-xl border bg-card p-4">
          <h3 className="font-heading text-lg font-semibold">Recorded reviews</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Stored in this browser only. Export them and apply to the report with{" "}
            <code className="rounded bg-muted px-1 py-px font-mono">ccauditor review apply</code>.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={exportData.length === 0}
              onClick={() => downloadJson(`${model.report.id}.reviews.json`, exportData)}
            >
              <DownloadIcon /> Export reviews JSON
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={exportData.length === 0}
              onClick={() => {
                if (window.confirm("Delete all reviews recorded for this report in this browser?")) onClear();
              }}
            >
              <Trash2Icon /> Clear
            </Button>
          </div>
          {reviewed.length === 0 ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
              <InboxIcon className="size-4" aria-hidden /> No reviews yet.
            </div>
          ) : (
            <ul className="mt-4 divide-y text-sm">
              {reviewed.map((r) => (
                <li key={r.req.id} className="py-2.5">
                  <button type="button" onClick={() => onOpen(r.req.id)} className="w-full text-left">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="font-mono text-xs">{r.req.id}</span>
                      {r.review!.action === "override" && (
                        <>
                          <StatusBadge status={r.review!.original_status} className="opacity-60" />
                          <span aria-hidden className="text-muted-foreground">→</span>
                        </>
                      )}
                      <StatusBadge status={r.review!.status} />
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {r.review!.reviewer}, {fmtDate(r.review!.reviewed_at)}: {r.review!.justification}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {exportData.length > 0 && (
          <details className="rounded-xl border bg-card p-4 text-xs">
            <summary className="cursor-pointer font-medium">Preview export</summary>
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-2 font-mono">{JSON.stringify(exportData, null, 2)}</pre>
          </details>
        )}
      </aside>
    </div>
  );
}
