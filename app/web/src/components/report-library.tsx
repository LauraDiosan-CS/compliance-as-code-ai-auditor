"use client";

import { ArrowRightIcon, FileJsonIcon, HardDriveIcon, Loader2Icon, LibraryIcon, Trash2Icon, UploadIcon } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { RiskBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { fetchReportIndex, useAsync } from "@/lib/data";
import { MODE_LABEL, fmtDate, scoreTone } from "@/lib/meta";
import { normaliseReport } from "@/lib/scoring";
import { deleteUploadedReport, saveUploadedReport, useUploadedReports } from "@/lib/store";
import type { ReportIndexEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ReportLibrary() {
  const { data: library, error, loading } = useAsync(fetchReportIndex, ["index"]);
  const { uploads, hydrated } = useUploadedReports();

  const uploaded: ReportIndexEntry[] = Object.values(uploads).map((r) => ({
    id: r.id,
    target: r.target,
    created_at: r.created_at,
    mode: r.mode,
    policies: r.policies,
    risk_level: r.risk?.level ?? "unknown",
    overall_score: r.overall_score,
    requirements: r.requirements?.length,
    needs_review: r.verdicts?.filter((v) => v.status === "needs_review").length,
    source: "upload",
  }));

  return (
    <div className="space-y-10">
      <UploadZone />

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 font-heading text-xl font-semibold">
          <LibraryIcon className="size-5 text-muted-foreground" aria-hidden /> Library
        </h2>
        {loading && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2Icon className="size-4 animate-spin" aria-hidden /> Loading index...
          </p>
        )}
        {error && <p className="text-sm text-red-600">Could not load reports/index.json: {error}</p>}
        {library && library.length === 0 && <p className="text-sm text-muted-foreground">No published reports yet.</p>}
        {library && library.length > 0 && <ReportGrid entries={library} />}
      </section>

      {hydrated && uploaded.length > 0 && (
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 font-heading text-xl font-semibold">
            <HardDriveIcon className="size-5 text-muted-foreground" aria-hidden /> Uploaded in this browser
          </h2>
          <ReportGrid entries={uploaded} />
        </section>
      )}
    </div>
  );
}

function ReportGrid({ entries }: { entries: ReportIndexEntry[] }) {
  return (
    <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {entries.map((e) => (
        <li key={`${e.source}-${e.id}`}>
          <ReportCard entry={e} />
        </li>
      ))}
    </ul>
  );
}

function ReportCard({ entry: e }: { entry: ReportIndexEntry }) {
  const score = e.overall_score;
  return (
    <article className="group relative flex h-full flex-col rounded-xl border bg-card p-5 transition-shadow focus-within:ring-2 focus-within:ring-ring hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-[11px] text-muted-foreground">{e.id}</p>
          <h3 className="mt-1 font-heading text-lg leading-snug font-semibold break-all">
            <Link href={`/reports/${encodeURIComponent(e.id)}`} className="outline-none after:absolute after:inset-0">
              {e.target ?? e.id}
            </Link>
          </h3>
        </div>
        {typeof score === "number" && (
          <div className="text-right">
            <div className={cn("tabular font-heading text-3xl leading-none font-semibold", scoreTone(score))}>{Math.round(score)}</div>
            <div className="mt-1 text-[10px] tracking-wider text-muted-foreground uppercase">score</div>
          </div>
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {e.risk_level && <RiskBadge level={e.risk_level} className="px-2 py-0.5 text-[10px]" />}
        {e.mode && <span className="rounded border px-1.5 py-0.5 font-mono text-[11px]">{MODE_LABEL[e.mode] ?? e.mode}</span>}
        {e.policies?.map((p) => (
          <span key={p} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
            {p}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-5 text-xs text-muted-foreground">
        <span>{fmtDate(e.created_at)}</span>
        <span className="flex items-center gap-3">
          {typeof e.requirements === "number" && <span>{e.requirements} reqs</span>}
          {!!e.needs_review && <span className="text-violet-700 dark:text-violet-300">{e.needs_review} to review</span>}
          <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </span>
      </div>
      {e.source === "upload" && (
        <Button
          variant="ghost"
          size="icon-xs"
          className="absolute right-2 bottom-12 z-10"
          aria-label={`Remove uploaded report ${e.id}`}
          onClick={() => {
            if (window.confirm(`Remove uploaded report "${e.id}" from this browser?`)) deleteUploadedReport(e.id);
          }}
        >
          <Trash2Icon />
        </Button>
      )}
    </article>
  );
}

function UploadZone() {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string; id?: string } | null>(null);

  async function handle(files: FileList | null) {
    if (!files?.length) return;
    for (const f of Array.from(files)) {
      try {
        const report = normaliseReport(JSON.parse(await f.text()));
        saveUploadedReport(report);
        setMsg({ ok: true, text: `Loaded "${report.id}" (${report.requirements.length} requirements).`, id: report.id });
      } catch (err) {
        setMsg({ ok: false, text: `${f.name}: ${err instanceof Error ? err.message : "invalid JSON"}` });
      }
    }
    if (input.current) input.current.value = "";
  }

  return (
    <section aria-labelledby="upload-title">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void handle(e.dataTransfer.files);
        }}
        className={cn(
          "bg-ledger flex flex-col items-start gap-4 rounded-xl border-2 border-dashed p-6 transition-colors sm:flex-row sm:items-center",
          drag ? "border-primary bg-accent/50" : "border-border",
        )}
      >
        <FileJsonIcon className="size-10 shrink-0 text-primary" aria-hidden />
        <div className="flex-1">
          <h2 id="upload-title" className="font-heading text-lg font-semibold">
            Upload a report JSON
          </h2>
          <p className="text-sm text-muted-foreground">
            Drop the JSON written by{" "}
            <code className="rounded bg-muted px-1 font-mono text-xs">ccauditor audit ./repo --format json --out report.json</code>{" "}
            here. It is parsed in the browser and stored in localStorage; nothing is sent to a server.
          </p>
        </div>
        <input ref={input} type="file" accept="application/json,.json" multiple className="sr-only" id="report-file" onChange={(e) => void handle(e.target.files)} />
        <Button onClick={() => input.current?.click()}>
          <UploadIcon /> Choose file
        </Button>
      </div>
      {msg && (
        <p role="status" className={cn("mt-2 text-sm", msg.ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400")}>
          {msg.text}{" "}
          {msg.id && (
            <Link href={`/reports/${encodeURIComponent(msg.id)}`} className="font-medium underline">
              Open report
            </Link>
          )}
        </p>
      )}
    </section>
  );
}
