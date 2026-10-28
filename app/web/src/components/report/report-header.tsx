import { CalendarIcon, FileSearchIcon, GitBranchIcon, ScaleIcon, TimerIcon, UserCheckIcon } from "lucide-react";
import { RiskBadge } from "@/components/badges";
import { MODE_LABEL, RISK_META, fmtDate } from "@/lib/meta";
import type { ReportModel } from "@/lib/report-model";
import { ScoreGauge } from "./score-gauge";

function stat(stats: Record<string, unknown>, key: string): string | null {
  const v = stats[key];
  if (v === undefined || v === null || v === "") return null;
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en") : v.toFixed(1);
  return typeof v === "object" ? null : String(v);
}

export function ReportHeader({ model, onEvidence }: { model: ReportModel; onEvidence?: (id: string) => void }) {
  const { report, overall, adjusted } = model;
  const risk = report.risk;
  const meta = [
    { icon: CalendarIcon, label: "Audited", value: fmtDate(report.created_at) },
    { icon: ScaleIcon, label: "Mode", value: MODE_LABEL[report.mode] ?? report.mode },
    { icon: FileSearchIcon, label: "Files scanned", value: stat(report.stats, "files_scanned") },
    { icon: TimerIcon, label: "Duration", value: stat(report.stats, "duration_s") ? `${stat(report.stats, "duration_s")} s` : null },
  ].filter((m) => m.value);

  return (
    <section className="grid gap-6 rounded-xl border bg-card p-5 shadow-xs sm:p-6 lg:grid-cols-[1fr_auto]">
      <div className="min-w-0 space-y-4">
        <div className="space-y-1.5">
          <p className="font-mono text-xs break-all text-muted-foreground">{report.id}</p>
          <h1 className="flex items-start gap-2 font-heading text-2xl font-semibold tracking-tight break-all sm:text-3xl">
            <GitBranchIcon className="mt-1.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
            {report.target}
          </h1>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {report.policies.map((p) => (
              <span key={p} className="rounded border bg-background px-2 py-0.5 font-mono text-xs">
                {p}
              </span>
            ))}
          </div>
        </div>

        <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {meta.map((m) => (
            <div key={m.label} className="flex items-center gap-1.5">
              <m.icon className="size-3.5 text-muted-foreground" aria-hidden />
              <dt className="text-muted-foreground">{m.label}</dt>
              <dd className="tabular font-medium">{m.value}</dd>
            </div>
          ))}
        </dl>

        {risk && (
          <div className="rounded-lg border border-dashed bg-muted/40 p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium tracking-wider text-muted-foreground uppercase">AI Act risk level</span>
              <RiskBadge level={risk.level} />
              <span className="text-xs text-muted-foreground">{RISK_META[risk.level]?.blurb}</span>
              {risk.confidence > 0 && (
                <span className="tabular ml-auto font-mono text-xs text-muted-foreground">conf. {(risk.confidence * 100).toFixed(0)}%</span>
              )}
            </div>
            <p className="text-sm leading-relaxed text-pretty">{risk.rationale}</p>
            {(risk.triggers.length > 0 || risk.evidence_ids.length > 0) && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {risk.triggers.map((t) => (
                  <span key={t} className="rounded-md bg-orange-500/10 px-2 py-0.5 text-xs text-orange-900 ring-1 ring-orange-600/20 ring-inset dark:text-orange-200">
                    {t}
                  </span>
                ))}
                {risk.evidence_ids.map((id) => {
                  const ev = model.evidenceById.get(id);
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => onEvidence?.(id)}
                      className="rounded-md px-2 py-0.5 font-mono text-xs text-muted-foreground ring-1 ring-border ring-inset hover:bg-muted hover:text-foreground"
                    >
                      {ev ? `${ev.path}:L${ev.start_line}-L${ev.end_line}` : id}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col items-center justify-center gap-2 lg:border-l lg:pl-6">
        <ScoreGauge score={overall} />
        {adjusted ? (
          <p className="flex max-w-48 items-center gap-1.5 text-center text-xs text-muted-foreground">
            <UserCheckIcon className="size-3.5 shrink-0" aria-hidden />
            Adjusted by human review (pipeline: {report.overall_score.toFixed(1)})
          </p>
        ) : (
          <p className="max-w-48 text-center text-xs text-muted-foreground">Severity-weighted, excluding N/A</p>
        )}
      </div>
    </section>
  );
}
