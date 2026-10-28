import {
  ArrowRightIcon,
  BookOpenTextIcon,
  CheckCheckIcon,
  FileCode2Icon,
  FileTextIcon,
  GaugeIcon,
  ListChecksIcon,
  type LucideIcon,
  NetworkIcon,
  ScaleIcon,
  SearchCodeIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  UserCheckIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { STATUS_META } from "@/lib/meta";
import { STATUSES } from "@/lib/types";

const PIPELINE: { icon: LucideIcon; title: string; body: string; out: string }[] = [
  {
    icon: BookOpenTextIcon,
    title: "Policy",
    body: "EU AI Act, GDPR or an internal policy in Markdown is parsed into citable clauses.",
    out: "eu-ai-act/Art.12(1)",
  },
  {
    icon: ListChecksIcon,
    title: "Requirements",
    body: "Clauses become testable requirements with a category, severity, rule checks and LLM guidance.",
    out: "AIA-REC-01",
  },
  {
    icon: SearchCodeIcon,
    title: "Evidence",
    body: "Collectors index code, config, IaC, docs, model cards and logs; a BM25 retriever ranks candidates.",
    out: "src/service.py:L41-L58",
  },
  {
    icon: ScaleIcon,
    title: "Verdicts",
    body: "Rules and an LLM judge decide each requirement, citing evidence ids. Borderline calls go to humans.",
    out: "partial · 0.78",
  },
  {
    icon: GaugeIcon,
    title: "Report",
    body: "JSON, Markdown, SARIF and this dashboard: scorecard, risk level, gaps and remediation.",
    out: "score 64.8",
  },
];

const AGENTS: { icon: LucideIcon; name: string; role: string }[] = [
  { icon: FileTextIcon, name: "PolicyAnalyst", role: "Decomposes clauses into verifiable requirements with categories, retrieval queries and judging guidance." },
  { icon: ShieldAlertIcon, name: "RiskClassifier", role: "Places the system in an AI Act tier (prohibited, high, limited, minimal) using Art. 5, Art. 6 with Annex III, and Art. 50." },
  { icon: SearchCodeIcon, name: "EvidenceScout", role: "Expands queries and selects the most relevant evidence for each requirement." },
  { icon: ScaleIcon, name: "ComplianceJudge", role: "Decides status, rationale and gaps, and must cite the evidence ids it relied on." },
  { icon: ShieldCheckIcon, name: "Verifier", role: "Checks that every cited id exists and that the snippet supports the claim. Unsupported verdicts are downgraded." },
  { icon: WrenchIcon, name: "Remediator", role: "Writes remediation steps and drafts missing artefacts such as tech-doc sections or risk templates." },
  { icon: NetworkIcon, name: "Orchestrator", role: "Plans the run, routes deterministic or LLM evaluation, aggregates results and enforces human review." },
];

const MODES = [
  { name: "Deterministic", body: "YAML and Rego rules only. Reproducible, runs in CI, no model calls." },
  { name: "Hybrid", body: "Rules first; the LLM handles ambiguous requirements; every citation is verified." },
  { name: "LLM", body: "LLM judge on retrieved evidence for all requirements. Used as a baseline." },
];

export default function Home() {
  return (
    <div>
      {/* hero */}
      <section className="bg-ledger overflow-hidden border-b">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div className="space-y-6">
            <p className="font-mono text-xs tracking-[0.18em] text-muted-foreground uppercase">Compliance-as-Code AI Auditor</p>
            <h1 className="font-heading text-4xl leading-[1.08] font-semibold tracking-tight sm:text-5xl">
              Every requirement linked to evidence, <span className="text-primary italic">or to a gap</span>.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
              CCAuditor reads an application repository against the EU AI Act, GDPR and internal policies, and produces an
              auditable report with file-and-line citations, a category scorecard, an AI Act risk level and remediation.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/reports" className={buttonVariants({ size: "lg", className: "px-4" })}>
                Browse reports <ArrowRightIcon />
              </Link>
              <Link href="/audit" className={buttonVariants({ size: "lg", variant: "outline", className: "px-4" })}>
                Run an audit
              </Link>
            </div>
          </div>
          <SampleFinding />
        </div>
      </section>

      {/* pipeline */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <SectionTitle kicker="Pipeline" title="From policy text to a traceable verdict" />
        <ol className="mt-8 grid gap-3 md:grid-cols-5">
          {PIPELINE.map((s, i) => (
            <li key={s.title} className="relative flex flex-col rounded-xl border bg-card p-4">
              <div className="flex items-center gap-2">
                <span className="tabular font-mono text-xs text-muted-foreground">0{i + 1}</span>
                <s.icon className="size-4 text-primary" aria-hidden />
                <h3 className="font-heading text-lg font-semibold">{s.title}</h3>
              </div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              <code className="mt-3 truncate rounded bg-muted px-2 py-1 font-mono text-[11px]">{s.out}</code>
              {i < PIPELINE.length - 1 && (
                <ArrowRightIcon className="absolute top-1/2 -right-3 z-10 hidden size-4 -translate-y-1/2 rounded-full bg-background text-muted-foreground md:block" aria-hidden />
              )}
            </li>
          ))}
        </ol>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {MODES.map((m) => (
            <div key={m.name} className="rounded-lg border border-dashed p-4 text-sm">
              <span className="font-mono text-xs font-semibold tracking-wider uppercase">{m.name} mode</span>
              <p className="mt-1 text-muted-foreground">{m.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* agents */}
      <section className="border-y bg-muted/30">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <SectionTitle
            kicker="Agents"
            title="Seven narrow agents, one orchestrated run"
            body="Each agent has a single responsibility and a typed contract. The LLM backend is Claude Code in headless mode; tests use a deterministic fake backend."
          />
          <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {AGENTS.map((a) => (
              <li key={a.name} className="rounded-xl border bg-card p-4 last:sm:col-span-2 last:lg:col-span-1">
                <a.icon className="size-5 text-primary" aria-hidden />
                <h3 className="mt-3 font-mono text-sm font-semibold">{a.name}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{a.role}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* statuses + HITL */}
      <section className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 [&>*]:min-w-0">
        <div>
          <SectionTitle kicker="Verdicts" title="Five statuses, scored consistently" />
          <ul className="mt-6 space-y-2">
            {STATUSES.map((s) => (
              <li key={s} className="flex items-center gap-3 text-sm">
                <span className="size-3 rounded-sm" style={{ background: STATUS_META[s].color }} aria-hidden />
                <span className="w-32 shrink-0 font-medium">{STATUS_META[s].label}</span>
                <span className="text-muted-foreground">
                  {s === "compliant" && "full credit"}
                  {s === "partial" && "half credit"}
                  {s === "non_compliant" && "no credit, gap and remediation reported"}
                  {s === "needs_review" && "no credit until a human decides"}
                  {s === "not_applicable" && "excluded from the score"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-muted-foreground">
            Category score = (compliant + 0.5 × partial) / applicable × 100. The overall score weights requirements by
            severity: critical 4, high 3, medium 2, low 1.
          </p>
        </div>
        <div className="rounded-xl border bg-card p-6">
          <UserCheckIcon className="size-6 text-violet-600 dark:text-violet-400" aria-hidden />
          <h3 className="mt-3 font-heading text-2xl font-semibold">Human-in-the-loop by design</h3>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Low-confidence or conflicting verdicts are never forced into pass or fail. They land in a review queue where a
            named reviewer accepts or overrides them with a written justification. Reviews are exported as JSON and applied
            with <code className="font-mono text-xs">ccauditor review apply</code>, so the final report records who decided
            what, and why.
          </p>
          <Link href="/reports" className={buttonVariants({ variant: "outline", className: "mt-5" })}>
            <CheckCheckIcon /> Open the review queue of a sample report
          </Link>
        </div>
      </section>
    </div>
  );
}

function SectionTitle({ kicker, title, body }: { kicker: string; title: string; body?: string }) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-xs tracking-[0.18em] text-muted-foreground uppercase">{kicker}</p>
      <h2 className="mt-2 font-heading text-3xl font-semibold tracking-tight">{title}</h2>
      {body && <p className="mt-2 text-muted-foreground">{body}</p>}
    </div>
  );
}

/** Static illustration of a single finding as it appears in a report. */
function SampleFinding() {
  return (
    <figure aria-label="Example finding" className="rotate-[0.4deg] rounded-xl border bg-card shadow-lg shadow-black/5">
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <span className="font-mono text-xs font-semibold">AIA-REC-02</span>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-800 ring-1 ring-red-600/25 ring-inset dark:text-red-300">
          <span className="size-1.5 rounded-full bg-red-500" /> Non-compliant
        </span>
      </div>
      <div className="space-y-3 p-4">
        <p className="font-heading text-[15px] leading-snug">Automatically generated logs are retained for at least 180 days.</p>
        <p className="font-mono text-[11px] text-muted-foreground">eu-ai-act/Art.19(1)</p>
        <div className="overflow-hidden rounded-md border">
          <div className="flex items-center gap-1.5 border-b bg-muted/60 px-2.5 py-1 font-mono text-[11px]">
            <FileCode2Icon className="size-3" aria-hidden /> config/logging.yaml<span className="text-muted-foreground">:L1-L12</span>
          </div>
          <pre className="px-3 py-2 font-mono text-[12px] leading-relaxed">
            <span className="tok-key">sinks</span>:{"\n"}
            {"  "}- <span className="tok-key">type</span>: cloudwatch{"\n"}
            <span className="bg-red-500/15">
              <span className="tok-key">retention_days</span>: <span className="tok-num">30</span>
            </span>
          </pre>
        </div>
        <p className="flex gap-2 text-sm">
          <WrenchIcon className="mt-0.5 size-4 shrink-0 text-emerald-700 dark:text-emerald-400" aria-hidden />
          Set retention to at least 180 days, matching the CloudWatch log group.
        </p>
      </div>
    </figure>
  );
}
