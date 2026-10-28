import { applyReviews, computeScores, statusCounts } from "./scoring";
import type {
  AuditReport,
  CategoryScore,
  Clause,
  Evidence,
  PolicyWithRequirements,
  Requirement,
  Status,
  StoredReview,
  Verdict,
} from "./types";

export interface Row {
  req: Requirement;
  verdict: Verdict | undefined; // effective (after human review)
  original: Verdict | undefined; // as produced by the pipeline
  review: StoredReview | undefined;
  evidence: Evidence[]; // resolved citations
  missingCitations: string[]; // cited ids not present in report.evidence
}

export interface ReportModel {
  report: AuditReport;
  rows: Row[];
  rowById: Map<string, Row>;
  evidenceById: Map<string, Evidence>;
  clauses: Map<string, Clause>;
  scorecard: CategoryScore[];
  overall: number;
  adjusted: boolean; // scores recomputed due to human reviews
  counts: Record<Status, number>;
  reviewCount: number;
}

const PRIORITY: Record<Status, number> = { non_compliant: 0, needs_review: 1, partial: 2, compliant: 3, not_applicable: 4 };
const SEV: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function rowPriority(r: Row): number {
  return (r.verdict ? PRIORITY[r.verdict.status] : 1) * 10 + (SEV[r.req.severity] ?? 2);
}

export function buildModel(
  report: AuditReport,
  reviews: Record<string, StoredReview>,
  policies: PolicyWithRequirements[] | null,
): ReportModel {
  const evidenceById = new Map(report.evidence.map((e) => [e.id, e]));
  const effective = applyReviews(report.verdicts, reviews);
  const origBy = new Map(report.verdicts.map((v) => [v.requirement_id, v]));
  const effBy = new Map(effective.map((v) => [v.requirement_id, v]));

  const rows: Row[] = report.requirements.map((req) => {
    const verdict = effBy.get(req.id);
    const ids = verdict?.evidence_ids ?? [];
    return {
      req,
      verdict,
      original: origBy.get(req.id),
      review: reviews[req.id],
      evidence: ids.map((id) => evidenceById.get(id)).filter((e): e is Evidence => !!e),
      missingCitations: ids.filter((id) => !evidenceById.has(id)),
    };
  });

  const reviewCount = rows.filter((r) => r.review).length;
  const changed = rows.some((r) => r.review && r.verdict?.status !== r.original?.status);
  const useComputed = reviewCount > 0 || report.scorecard.length === 0;
  const computed = useComputed ? computeScores(report.requirements, effective) : null;

  const clauses = new Map<string, Clause>();
  for (const p of policies ?? []) for (const c of p.clauses ?? []) clauses.set(c.id, c);

  return {
    report,
    rows,
    rowById: new Map(rows.map((r) => [r.req.id, r])),
    evidenceById,
    clauses,
    scorecard: computed ? computed.scorecard : report.scorecard,
    overall: computed ? computed.overall : report.overall_score,
    adjusted: changed,
    counts: statusCounts(effective),
    reviewCount,
  };
}
