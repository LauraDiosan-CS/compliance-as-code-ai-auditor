import type { Category, EvidenceKind, RiskLevel, Severity, Status, VerdictMethod } from "./types";

interface StatusMeta {
  label: string;
  short: string;
  color: string; // chart / svg color (works in light & dark)
  badge: string; // tailwind classes for pills
  dot: string;
}

export const STATUS_META: Record<Status, StatusMeta> = {
  compliant: {
    label: "Compliant",
    short: "Pass",
    color: "#10b981",
    badge: "bg-emerald-500/10 text-emerald-800 ring-emerald-600/25 dark:text-emerald-300 dark:ring-emerald-400/30",
    dot: "bg-emerald-500",
  },
  partial: {
    label: "Partial",
    short: "Partial",
    color: "#f59e0b",
    badge: "bg-amber-500/12 text-amber-800 ring-amber-600/30 dark:text-amber-300 dark:ring-amber-400/30",
    dot: "bg-amber-500",
  },
  non_compliant: {
    label: "Non-compliant",
    short: "Fail",
    color: "#ef4444",
    badge: "bg-red-500/10 text-red-800 ring-red-600/25 dark:text-red-300 dark:ring-red-400/30",
    dot: "bg-red-500",
  },
  needs_review: {
    label: "Needs review",
    short: "Review",
    color: "#8b5cf6",
    badge: "bg-violet-500/10 text-violet-800 ring-violet-600/25 dark:text-violet-300 dark:ring-violet-400/30",
    dot: "bg-violet-500",
  },
  not_applicable: {
    label: "Not applicable",
    short: "N/A",
    color: "#a1a1aa",
    badge: "bg-zinc-500/10 text-zinc-700 ring-zinc-500/25 dark:text-zinc-300 dark:ring-zinc-400/25",
    dot: "bg-zinc-400",
  },
};

export const RISK_META: Record<RiskLevel, { label: string; badge: string; blurb: string }> = {
  prohibited: {
    label: "Prohibited",
    badge: "bg-red-600 text-white dark:bg-red-500",
    blurb: "Art. 5 prohibited practice",
  },
  high: {
    label: "High risk",
    badge: "bg-orange-600 text-white dark:bg-orange-500 dark:text-black",
    blurb: "Art. 6 / Annex III high-risk system",
  },
  limited: {
    label: "Limited risk",
    badge: "bg-sky-600 text-white dark:bg-sky-400 dark:text-black",
    blurb: "Art. 50 transparency obligations",
  },
  minimal: {
    label: "Minimal risk",
    badge: "bg-emerald-600 text-white dark:bg-emerald-400 dark:text-black",
    blurb: "No specific AI Act obligations",
  },
  unknown: {
    label: "Unclassified",
    badge: "bg-zinc-500 text-white",
    blurb: "Risk level could not be determined",
  },
};

export const SEVERITY_META: Record<Severity, { label: string; weight: number; cls: string }> = {
  critical: { label: "Critical", weight: 4, cls: "text-red-700 dark:text-red-300" },
  high: { label: "High", weight: 3, cls: "text-orange-700 dark:text-orange-300" },
  medium: { label: "Medium", weight: 2, cls: "text-foreground/80" },
  low: { label: "Low", weight: 1, cls: "text-muted-foreground" },
};

export const METHOD_META: Record<VerdictMethod, { label: string; hint: string }> = {
  deterministic: { label: "Rules", hint: "Deterministic rule engine (regex / file / YAML / Rego checks)" },
  llm: { label: "LLM", hint: "LLM judge with retrieved evidence" },
  hybrid: { label: "Hybrid", hint: "Rules first, LLM for ambiguous parts, citations verified" },
  human: { label: "Human", hint: "Decided by a human reviewer" },
};

export const CATEGORY_LABEL: Record<Category, string> = {
  risk_classification: "Risk classification",
  transparency: "Transparency",
  record_keeping: "Record-keeping",
  human_oversight: "Human oversight",
  data_governance: "Data governance",
  technical_documentation: "Technical docs",
  accuracy_robustness: "Accuracy & robustness",
  security: "Security",
  data_retention: "Data retention",
  other: "Other",
};

export const EVIDENCE_KIND_LABEL: Record<EvidenceKind, string> = {
  code: "Code",
  config: "Config",
  iac: "IaC",
  doc: "Doc",
  model_card: "Model card",
  log: "Log",
};

export const MODE_LABEL: Record<string, string> = {
  deterministic: "Deterministic",
  hybrid: "Hybrid",
  llm: "LLM",
};

export function label<T extends string>(map: Record<T, string>, key: string): string {
  return (map as Record<string, string>)[key] ?? key.replace(/_/g, " ");
}

export function fmtDate(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export function scoreTone(score: number): string {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function scoreColor(score: number): string {
  if (score >= 80) return STATUS_META.compliant.color;
  if (score >= 50) return STATUS_META.partial.color;
  return STATUS_META.non_compliant.color;
}
