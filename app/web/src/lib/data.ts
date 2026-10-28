"use client";

import { useEffect, useState } from "react";
import { normaliseReport } from "./scoring";
import { getUploadedReports } from "./store";
import type { AuditReport, PolicyWithRequirements, ReportIndexEntry } from "./types";

// Static JSON lives in /public and is fetched at runtime, so the orchestrator can
// regenerate it without touching code:
//   public/reports/index.json   -> { reports: ReportIndexEntry[] }  (a bare array is accepted too)
//   public/reports/<file>.json  -> AuditReport
//   public/policies/index.json  -> { policies: PolicyWithRequirements[] } (bare array accepted;
//                                  entries may point at a `file` with the full policy)

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function fetchReportIndex(): Promise<ReportIndexEntry[]> {
  const raw = await getJson<unknown>("/reports/index.json");
  const list = Array.isArray(raw) ? raw : ((raw as { reports?: unknown[] })?.reports ?? []);
  return (list as (ReportIndexEntry | string)[])
    .map((e) => (typeof e === "string" ? { id: e.replace(/\.json$/, ""), file: e } : e))
    .filter((e): e is ReportIndexEntry => !!e && typeof e.id === "string")
    .map((e) => ({ ...e, source: "library" as const }));
}

export async function fetchReport(id: string): Promise<AuditReport> {
  const uploaded = getUploadedReports()[id];
  if (uploaded) return normaliseReport(uploaded);
  let file = `${id}.json`;
  try {
    const entry = (await fetchReportIndex()).find((e) => e.id === id);
    if (entry?.file) file = entry.file;
  } catch {
    // index missing: fall back to <id>.json
  }
  const path = file.startsWith("/") ? file : `/reports/${file.replace(/^(\.\/)?(reports\/)?/, "")}`;
  return normaliseReport(await getJson<unknown>(path));
}

export async function fetchPolicies(): Promise<PolicyWithRequirements[]> {
  const raw = await getJson<unknown>("/policies/index.json");
  const list = (Array.isArray(raw) ? raw : ((raw as { policies?: unknown[] })?.policies ?? [])) as PolicyWithRequirements[];
  // `ccauditor policies --json` style entries carry counts instead of arrays; ignore non-array fields
  for (const p of list) {
    if (p.requirements && !Array.isArray(p.requirements)) delete p.requirements;
    if (p.clauses && !Array.isArray(p.clauses)) delete p.clauses;
  }
  return Promise.all(
    list.map(async (p) => {
      if (p.file && !p.requirements) {
        const path = p.file.startsWith("/") ? p.file : `/policies/${p.file}`;
        try {
          const detail = await getJson<Record<string, unknown>>(path);
          // accept either a flat Policy (+requirements) or the API shape { policy, requirements }
          const flat = (detail.policy ? { ...(detail.policy as object), requirements: detail.requirements } : detail) as Partial<PolicyWithRequirements>;
          return { ...p, ...flat };
        } catch {
          return p;
        }
      }
      return p;
    }),
  );
}

type Async<T> = { data: T | null; error: string | null; loading: boolean };

/** Minimal async loader hook (state only updated from async callbacks). */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T> & { key: string }>({ data: null, error: null, loading: true, key: "" });
  const key = JSON.stringify(deps);
  useEffect(() => {
    let alive = true;
    fn().then(
      (data) => alive && setState({ data, error: null, loading: false, key }),
      (e: unknown) => alive && setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false, key }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  if (state.key !== key) return { data: null, error: null, loading: true };
  return state;
}
