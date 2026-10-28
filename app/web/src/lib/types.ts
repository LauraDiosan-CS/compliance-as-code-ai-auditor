// TypeScript mirror of app/backend/ccauditor/models.py (the AuditReport JSON contract).
// Keep field names identical to the Python models.

export type RiskLevel = "prohibited" | "high" | "limited" | "minimal" | "unknown";

export type Category =
  | "risk_classification"
  | "transparency"
  | "record_keeping"
  | "human_oversight"
  | "data_governance"
  | "technical_documentation"
  | "accuracy_robustness"
  | "security"
  | "data_retention"
  | "other";

export type Status = "compliant" | "non_compliant" | "partial" | "needs_review" | "not_applicable";

export type EvidenceKind = "code" | "config" | "iac" | "doc" | "model_card" | "log";

export type Severity = "critical" | "high" | "medium" | "low";

export type VerdictMethod = "deterministic" | "llm" | "hybrid" | "human";

export type AuditMode = "deterministic" | "llm" | "hybrid";

export const RISK_LEVELS: RiskLevel[] = ["prohibited", "high", "limited", "minimal", "unknown"];
export const CATEGORIES: Category[] = [
  "risk_classification",
  "transparency",
  "record_keeping",
  "human_oversight",
  "data_governance",
  "technical_documentation",
  "accuracy_robustness",
  "security",
  "data_retention",
  "other",
];
export const STATUSES: Status[] = ["compliant", "partial", "non_compliant", "needs_review", "not_applicable"];
export const EVIDENCE_KINDS: EvidenceKind[] = ["code", "config", "iac", "doc", "model_card", "log"];
export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];
export const METHODS: VerdictMethod[] = ["deterministic", "llm", "hybrid", "human"];
export const MODES: AuditMode[] = ["deterministic", "hybrid", "llm"];

// ---------------------------------------------------------------- policy side

export interface Clause {
  id: string; // e.g. "eu-ai-act/Art.12(1)"
  policy_id: string;
  title: string;
  text: string;
  parent_id: string | null;
}

export interface Policy {
  id: string;
  name: string;
  version: string;
  source: string;
  kind: "regulation" | "internal_policy" | "control_framework";
  clauses: Clause[];
}

export interface RuleCheck {
  type: "pattern" | "file_exists" | "yaml_path" | "rego";
  description: string;
  globs: string[];
  kinds: EvidenceKind[];
  pattern: string | null;
  path: string | null;
  equals: unknown;
  rego: string | null;
  expect: "present" | "absent";
}

export interface Requirement {
  id: string;
  policy_id: string;
  clause_ids: string[];
  category: Category;
  title: string;
  statement: string;
  applies_to: RiskLevel[];
  checks: RuleCheck[];
  llm_guidance: string;
  evidence_queries: string[];
  severity: Severity;
}

// ---------------------------------------------------------------- evidence side

export interface Evidence {
  id: string;
  kind: EvidenceKind;
  path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  signal: string;
  score: number;
}

export interface EvidenceIndex {
  repo_root: string;
  files_scanned: number;
  items: Evidence[];
}

// ---------------------------------------------------------------- verdicts & report

export interface Verdict {
  requirement_id: string;
  status: Status;
  confidence: number; // 0..1
  rationale: string;
  evidence_ids: string[];
  gaps: string[];
  remediation: string;
  method: VerdictMethod;
  verified: boolean;
}

export interface RiskAssessment {
  level: RiskLevel;
  rationale: string;
  triggers: string[];
  evidence_ids: string[];
  confidence: number;
}

export interface CategoryScore {
  category: Category;
  total: number;
  compliant: number;
  partial: number;
  non_compliant: number;
  needs_review: number;
  score: number; // 0..100
}

export interface AuditReport {
  id: string;
  created_at: string; // ISO datetime
  target: string;
  policies: string[];
  mode: AuditMode;
  risk: RiskAssessment | null;
  requirements: Requirement[];
  verdicts: Verdict[];
  evidence: Evidence[];
  scorecard: CategoryScore[];
  overall_score: number;
  stats: Record<string, unknown>;
}

// ---------------------------------------------------------------- web-only types

/** Entry of public/reports/index.json. Only `id` is required; `file` defaults to `${id}.json`. */
export interface ReportIndexEntry {
  id: string;
  file?: string;
  target?: string;
  created_at?: string;
  mode?: AuditMode;
  policies?: string[];
  risk_level?: RiskLevel;
  overall_score?: number;
  requirements?: number;
  needs_review?: number;
  source?: "library" | "upload";
}

/** Human review decision; export format consumed by `ccauditor review apply`. */
export interface ReviewDecision {
  requirement_id: string;
  status: Status;
  reviewer: string;
  justification: string;
  reviewed_at: string;
}

/** Stored locally; `action` is UI metadata (not exported). */
export interface StoredReview extends ReviewDecision {
  action: "accept" | "override";
  original_status: Status;
}

/** Policy entry in public/policies/index.json (Policy + its requirements). */
export interface PolicyWithRequirements extends Partial<Policy> {
  id: string;
  name: string;
  file?: string;
  requirements?: Requirement[];
}
