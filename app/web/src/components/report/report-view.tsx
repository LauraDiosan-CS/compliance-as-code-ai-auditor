"use client";

import { ArrowLeftIcon, DownloadIcon, Loader2Icon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CodeSnippet } from "@/components/code-snippet";
import { Button, buttonVariants } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchPolicies, fetchReport, useAsync } from "@/lib/data";
import { buildModel } from "@/lib/report-model";
import { downloadJson, useReviews } from "@/lib/store";
import type { AuditReport, Status } from "@/lib/types";
import { CategoryChart, StatusDistribution } from "./charts";
import { ReportHeader } from "./report-header";
import { RequirementSheet } from "./requirement-sheet";
import { EMPTY_FILTERS, type Filters, RequirementsTable } from "./requirements-table";
import { ReviewQueue } from "./review-queue";
import { TopFindings, Traceability } from "./traceability";

export function ReportView({ id }: { id: string }) {
  const { data: report, error, loading } = useAsync(() => fetchReport(id), [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-32 text-muted-foreground" role="status">
        <Loader2Icon className="size-4 animate-spin" aria-hidden /> Loading report...
      </div>
    );
  }
  if (error || !report) {
    return (
      <div className="mx-auto max-w-lg py-24 text-center">
        <h1 className="font-heading text-2xl font-semibold">Report not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          <code className="font-mono">{id}</code> is not in the library or in this browser&apos;s uploads.
          {error && <span className="mt-1 block font-mono text-xs">{error}</span>}
        </p>
        <Link href="/reports" className={buttonVariants({ variant: "outline", className: "mt-6" })}>
          <ArrowLeftIcon /> Back to reports
        </Link>
      </div>
    );
  }
  return <LoadedReport report={report} />;
}

function Panel({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-xl border bg-card p-5 ${className ?? ""}`}>
      <h2 className="mb-4 font-heading text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function LoadedReport({ report }: { report: AuditReport }) {
  const { reviews, saveReview, removeReview, clearReviews } = useReviews(report.id);
  const { data: policies } = useAsync(() => fetchPolicies().catch(() => []), ["policies"]);
  const model = useMemo(() => buildModel(report, reviews, policies), [report, reviews, policies]);

  const [tab, setTab] = useState<string>("overview");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [openReq, setOpenReq] = useState<string | null>(null);
  const [openEv, setOpenEv] = useState<string | null>(null);

  const pendingCount = model.rows.filter((r) => !r.review && (r.original?.status ?? "needs_review") === "needs_review").length;
  const showStatus = (s: Status) => {
    setFilters({ ...EMPTY_FILTERS, status: s });
    setTab("requirements");
  };
  const ev = openEv ? model.evidenceById.get(openEv) : undefined;
  const stats = Object.entries(report.stats).filter(([, v]) => v !== null && typeof v !== "object");

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link href="/reports" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="size-4" aria-hidden /> All reports
        </Link>
        <Button variant="outline" size="sm" onClick={() => downloadJson(`${report.id}.json`, report)}>
          <DownloadIcon /> Report JSON
        </Button>
      </div>

      <ReportHeader model={model} onEvidence={setOpenEv} />

      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <TabsList variant="line" className="h-10 gap-2">
            <TabsTrigger value="overview" className="px-2">Overview</TabsTrigger>
            <TabsTrigger value="requirements" className="px-2">
              Requirements <span className="tabular font-mono text-xs text-muted-foreground">{model.rows.length}</span>
            </TabsTrigger>
            <TabsTrigger value="traceability" className="px-2">Traceability</TabsTrigger>
            <TabsTrigger value="review" className="px-2">
              Review queue
              {pendingCount > 0 && (
                <span className="tabular rounded-full bg-violet-600 px-1.5 font-mono text-[11px] text-white">{pendingCount}</span>
              )}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            <Panel title="Category scorecard">
              <CategoryChart scorecard={model.scorecard} />
            </Panel>
            <Panel title="Status distribution">
              <StatusDistribution counts={model.counts} onSelect={showStatus} />
            </Panel>
          </div>
          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            <Panel title="Priority findings">
              <TopFindings model={model} onOpen={setOpenReq} />
            </Panel>
            <Panel title="Run statistics">
              {stats.length ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {stats.map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
                      <dd className="tabular text-right font-mono text-xs leading-5 break-all">
                        {typeof v === "number" ? v.toLocaleString("en") : String(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">No statistics recorded.</p>
              )}
            </Panel>
          </div>
        </TabsContent>

        <TabsContent value="requirements" className="mt-4">
          <RequirementsTable model={model} filters={filters} setFilters={setFilters} onOpen={setOpenReq} />
        </TabsContent>

        <TabsContent value="traceability" className="mt-4">
          <Traceability model={model} onOpen={setOpenReq} />
        </TabsContent>

        <TabsContent value="review" className="mt-4">
          <ReviewQueue model={model} reviews={reviews} onOpen={setOpenReq} onClear={clearReviews} />
        </TabsContent>
      </Tabs>

      <RequirementSheet model={model} reqId={openReq} onClose={() => setOpenReq(null)} onSave={saveReview} onRemove={removeReview} />

      <Sheet open={!!ev} onOpenChange={(o) => !o && setOpenEv(null)}>
        <SheetContent side="right" className="w-full overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
          <SheetHeader className="border-b pr-12">
            <SheetTitle className="font-heading text-lg">Risk classification evidence</SheetTitle>
          </SheetHeader>
          <div className="p-4">{ev && <CodeSnippet evidence={ev} maxLines={120} />}</div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
