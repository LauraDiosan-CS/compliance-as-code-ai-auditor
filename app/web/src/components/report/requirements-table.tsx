"use client";

import { SearchIcon, XIcon } from "lucide-react";
import { MethodTag, SeverityLabel, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CATEGORY_LABEL, METHOD_META, STATUS_META, label } from "@/lib/meta";
import { type ReportModel, type Row, rowPriority } from "@/lib/report-model";
import { SEVERITIES, STATUSES } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface Filters {
  q: string;
  status: string;
  category: string;
  severity: string;
  policy: string;
  method: string;
  sort: "priority" | "id";
}

export const EMPTY_FILTERS: Filters = { q: "", status: "", category: "", severity: "", policy: "", method: "", sort: "priority" };

export function filterRows(rows: Row[], f: Filters): Row[] {
  const q = f.q.trim().toLowerCase();
  const out = rows.filter((r) => {
    const v = r.verdict;
    if (f.status && (v?.status ?? "") !== f.status) return false;
    if (f.category && r.req.category !== f.category) return false;
    if (f.severity && r.req.severity !== f.severity) return false;
    if (f.policy && r.req.policy_id !== f.policy) return false;
    if (f.method && (v?.method ?? "") !== f.method) return false;
    if (q) {
      const hay = [r.req.id, r.req.title, r.req.statement, ...r.req.clause_ids, v?.rationale ?? "", ...(v?.gaps ?? []), ...r.evidence.map((e) => e.path)]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  return out.sort((a, b) => (f.sort === "id" ? a.req.id.localeCompare(b.req.id) : rowPriority(a) - rowPriority(b) || a.req.id.localeCompare(b.req.id)));
}

function FilterSelect({
  id,
  label: text,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label htmlFor={id} className="flex min-w-0 flex-col gap-1">
      <span className="text-[11px] font-medium tracking-wider text-muted-foreground uppercase">{text}</span>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "h-8 w-full min-w-0 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30",
          value && "border-primary/50 bg-accent/50",
        )}
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function RequirementsTable({
  model,
  filters,
  setFilters,
  onOpen,
}: {
  model: ReportModel;
  filters: Filters;
  setFilters: (f: Filters) => void;
  onOpen: (id: string) => void;
}) {
  const rows = filterRows(model.rows, filters);
  const set = (k: keyof Filters) => (v: string) => setFilters({ ...filters, [k]: v });
  const categories = [...new Set(model.rows.map((r) => r.req.category))];
  const policies = [...new Set(model.rows.map((r) => r.req.policy_id))];
  const methods = [...new Set(model.rows.map((r) => r.verdict?.method).filter(Boolean))] as string[];
  const active = (Object.keys(EMPTY_FILTERS) as (keyof Filters)[]).some((k) => k !== "sort" && filters[k] !== EMPTY_FILTERS[k]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 rounded-xl border bg-card p-3 sm:grid-cols-3 lg:grid-cols-[minmax(200px,2fr)_repeat(6,minmax(0,1fr))]">
        <label htmlFor="f-q" className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-1">
          <span className="text-[11px] font-medium tracking-wider text-muted-foreground uppercase">Search</span>
          <span className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input id="f-q" value={filters.q} onChange={(e) => set("q")(e.target.value)} placeholder="ID, clause, text, file path..." className="pl-8" />
          </span>
        </label>
        <FilterSelect id="f-status" label="Status" value={filters.status} onChange={set("status")} options={STATUSES.map((s) => ({ value: s, label: STATUS_META[s].label }))} />
        <FilterSelect id="f-cat" label="Category" value={filters.category} onChange={set("category")} options={categories.map((c) => ({ value: c, label: label(CATEGORY_LABEL, c) }))} />
        <FilterSelect id="f-sev" label="Severity" value={filters.severity} onChange={set("severity")} options={SEVERITIES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))} />
        <FilterSelect id="f-pol" label="Policy" value={filters.policy} onChange={set("policy")} options={policies.map((p) => ({ value: p, label: p }))} />
        <FilterSelect id="f-method" label="Method" value={filters.method} onChange={set("method")} options={methods.map((m) => ({ value: m, label: METHOD_META[m as keyof typeof METHOD_META]?.label ?? m }))} />
        <label htmlFor="f-sort" className="flex min-w-0 flex-col gap-1">
          <span className="text-[11px] font-medium tracking-wider text-muted-foreground uppercase">Sort</span>
          <select
            id="f-sort"
            value={filters.sort}
            onChange={(e) => setFilters({ ...filters, sort: e.target.value as Filters["sort"] })}
            className="h-8 w-full rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
          >
            <option value="priority">Priority</option>
            <option value="id">ID</option>
          </select>
        </label>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span aria-live="polite">
          {rows.length} of {model.rows.length} requirements
        </span>
        {active && (
          <Button variant="ghost" size="sm" onClick={() => setFilters({ ...EMPTY_FILTERS, sort: filters.sort })}>
            <XIcon /> Clear filters
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b bg-muted/50 text-left text-[11px] tracking-wider text-muted-foreground uppercase">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">ID</th>
              <th scope="col" className="px-3 py-2 font-medium">Requirement</th>
              <th scope="col" className="px-3 py-2 font-medium">Category</th>
              <th scope="col" className="px-3 py-2 font-medium">Severity</th>
              <th scope="col" className="px-3 py-2 font-medium">Status</th>
              <th scope="col" className="px-3 py-2 font-medium">Method</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Conf.</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Evid.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.req.id} className="group border-b last:border-0 hover:bg-muted/40">
                <td className="px-3 py-2.5 align-top font-mono text-xs whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => onOpen(r.req.id)}
                    className="rounded font-medium text-primary underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    {r.req.id}
                  </button>
                </td>
                <td className="max-w-md px-3 py-2.5 align-top">
                  <button type="button" onClick={() => onOpen(r.req.id)} className="text-left hover:underline" tabIndex={-1}>
                    <span className="font-medium">{r.req.title}</span>
                  </button>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{r.req.clause_ids.join(" · ")}</div>
                </td>
                <td className="px-3 py-2.5 align-top text-xs whitespace-nowrap text-muted-foreground">{label(CATEGORY_LABEL, r.req.category)}</td>
                <td className="px-3 py-2.5 align-top whitespace-nowrap">
                  <SeverityLabel severity={r.req.severity} />
                </td>
                <td className="px-3 py-2.5 align-top whitespace-nowrap">
                  <StatusBadge status={r.verdict?.status} />
                  {r.review && r.original && r.original.status !== r.verdict?.status && (
                    <div className="mt-1 text-[11px] text-muted-foreground line-through">{STATUS_META[r.original.status].label}</div>
                  )}
                </td>
                <td className="px-3 py-2.5 align-top whitespace-nowrap">{r.verdict && <MethodTag method={r.verdict.method} />}</td>
                <td className="tabular px-3 py-2.5 text-right align-top font-mono text-xs">
                  {r.verdict ? `${Math.round(r.verdict.confidence * 100)}%` : "-"}
                </td>
                <td className="tabular px-3 py-2.5 text-right align-top font-mono text-xs">
                  {r.evidence.length}
                  {r.missingCitations.length > 0 && <span className="text-red-600 dark:text-red-400" title="Unresolved citations"> !</span>}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-muted-foreground">
                  No requirements match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
