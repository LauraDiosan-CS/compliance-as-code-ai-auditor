import { SEVERITY_META } from "./meta";
import type { AuditReport, Category, CategoryScore, Requirement, Status, StoredReview, Verdict } from "./types";
import { CATEGORIES } from "./types";

/**
 * Apply local human reviews to the report's verdicts, mirroring
 * ccauditor.review.apply_reviews: status set by the reviewer, method = "human", confidence = 1.
 */
export function applyReviews(verdicts: Verdict[], reviews: Record<string, StoredReview>): Verdict[] {
  return verdicts.map((v) => {
    const r = reviews[v.requirement_id];
    if (!r) return v;
    return { ...v, status: r.status, method: "human", confidence: 1, gaps: r.status === "compliant" ? [] : v.gaps };
  });
}

function credit(status: Status): number {
  if (status === "compliant") return 1;
  if (status === "partial") return 0.5;
  return 0;
}

/**
 * Mirrors ccauditor.report.scoring.build_scorecard.
 * Category score = (compliant + 0.5 * partial) / applicable * 100; not_applicable excluded
 * (also from `total`); needs_review and missing verdicts count as 0. Categories with no
 * applicable requirement are omitted. Overall: severity-weighted (critical 4, high 3, medium 2, low 1).
 */
export function computeScores(
  requirements: Requirement[],
  verdicts: Verdict[],
): { scorecard: CategoryScore[]; overall: number } {
  const byReq = new Map(verdicts.map((v) => [v.requirement_id, v]));
  const buckets = new Map<Category, Status[]>();
  let num = 0;
  let den = 0;
  for (const r of requirements) {
    const status: Status = byReq.get(r.id)?.status ?? "needs_review";
    if (status === "not_applicable") continue;
    const list = buckets.get(r.category) ?? [];
    list.push(status);
    buckets.set(r.category, list);
    const w = SEVERITY_META[r.severity]?.weight ?? 2;
    den += w;
    num += w * credit(status);
  }
  const scorecard: CategoryScore[] = [];
  for (const category of CATEGORIES) {
    const st = buckets.get(category);
    if (!st?.length) continue;
    const n = (s: Status) => st.filter((x) => x === s).length;
    const c = n("compliant");
    const p = n("partial");
    scorecard.push({
      category,
      total: st.length,
      compliant: c,
      partial: p,
      non_compliant: n("non_compliant"),
      needs_review: n("needs_review"),
      score: round1(((c + 0.5 * p) / st.length) * 100),
    });
  }
  return { scorecard, overall: den ? round1((num / den) * 100) : 0 };
}

export function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

export function statusCounts(verdicts: Verdict[]): Record<Status, number> {
  const out: Record<Status, number> = {
    compliant: 0,
    partial: 0,
    non_compliant: 0,
    needs_review: 0,
    not_applicable: 0,
  };
  for (const v of verdicts) out[v.status] = (out[v.status] ?? 0) + 1;
  return out;
}

/** Number of applicable (non-N/A) requirements per category, for "n/a" display. */
export function applicableCount(c: CategoryScore): number {
  return c.compliant + c.partial + c.non_compliant + c.needs_review;
}

/** Validate and normalise an uploaded report JSON (fills defaults Pydantic would). */
export function normaliseReport(raw: unknown): AuditReport {
  if (!raw || typeof raw !== "object") throw new Error("File is not a JSON object.");
  const r = raw as Partial<AuditReport>;
  if (typeof r.id !== "string" || !r.id) throw new Error("Missing report `id`.");
  if (!Array.isArray(r.requirements)) throw new Error("Missing `requirements` array.");
  if (!Array.isArray(r.verdicts)) throw new Error("Missing `verdicts` array.");
  return {
    id: r.id,
    created_at: r.created_at ?? new Date().toISOString(),
    target: r.target ?? "(unknown target)",
    policies: r.policies ?? [],
    mode: r.mode ?? "deterministic",
    risk: r.risk ?? null,
    requirements: (r.requirements as Partial<Requirement>[]).map((q) => ({
      applies_to: ["high", "limited", "minimal"],
      checks: [],
      llm_guidance: "",
      evidence_queries: [],
      severity: "medium",
      category: "other",
      clause_ids: [],
      ...q,
    }) as Requirement),
    verdicts: (r.verdicts as Partial<Verdict>[]).map((v) => ({
      evidence_ids: [],
      gaps: [],
      remediation: "",
      method: "deterministic",
      verified: false,
      confidence: 0,
      rationale: "",
      ...v,
    }) as Verdict),
    evidence: r.evidence ?? [],
    scorecard: r.scorecard ?? [],
    overall_score: r.overall_score ?? 0,
    stats: r.stats ?? {},
  };
}
