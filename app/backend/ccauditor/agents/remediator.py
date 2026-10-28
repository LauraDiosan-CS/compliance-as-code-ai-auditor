"""Remediator / ArtifactGenerator: remediation text for gaps and drafts of missing compliance artefacts."""

from __future__ import annotations

from ..llm.backend import LLMBackend
from ..models import AuditReport, Evidence, Requirement, Status, Verdict
from .common import truncate

ARTIFACT_KINDS = ("technical_documentation", "risk_assessment", "transparency_notice", "model_card")

REMEDIATE_SYSTEM = """You are Remediator, a senior engineer helping an AI team close compliance gaps.
Given a requirement, the audit verdict and its gaps, propose concrete, minimal, repository-level remediation:
which files to add or change, what code/config/docs to write (short code sketches allowed). Do not claim anything is
already compliant. Answer with a single JSON object only."""

REMEDIATE_SCHEMA: dict = {
    "type": "object",
    "properties": {"remediation": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}},
    "required": ["remediation"],
}

ARTIFACT_SYSTEM = """You are ArtifactGenerator, a technical writer specialised in EU AI Act compliance documentation.
You draft compliance artefacts in Markdown for an AI system, based ONLY on the audit findings and evidence excerpts given.
Where information is missing, insert an explicit placeholder like "[TODO: describe ...]" instead of inventing facts.
Reference evidence as `path:start-end` when you use it. Answer with a single JSON object {"markdown": "..."} only."""

ARTIFACT_SCHEMA: dict = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
}

ARTIFACT_BRIEFS = {
    "technical_documentation": (
        "Technical documentation section following EU AI Act Annex IV: 1. general description (intended purpose, "
        "provider, versions, hardware/software), 2. detailed description of elements and development process (design "
        "choices, architecture, data requirements/datasheets, human oversight measures, validation & testing), "
        "3. monitoring, functioning and control (capabilities, limitations, accuracy levels), 4. risk management "
        "system (Art. 9), 5. lifecycle changes, 6. standards applied, 7. EU declaration of conformity placeholder, "
        "8. post-market monitoring plan."),
    "risk_assessment": (
        "Risk assessment / risk management record (Art. 9): system context and risk tier with justification, "
        "table of identified risks (hazard, affected persons, likelihood, severity, mitigation, residual risk, owner) "
        "derived from the audit gaps, testing and monitoring measures, review schedule."),
    "transparency_notice": (
        "User-facing transparency notice (Art. 50 and Art. 13): plain-language disclosure that users interact with "
        "an AI system, what it does and does not do, limitations, how outputs are generated/labelled, human contact "
        "and contestation route, data used. Short and readable."),
    "model_card": (
        "Model card (Mitchell et al. style): model details, intended use and out-of-scope uses, factors, metrics, "
        "evaluation data, training data, quantitative analyses, ethical considerations, caveats and recommendations."),
}


def _template_remediation(req: Requirement, verdict: Verdict) -> str:
    gaps = "; ".join(verdict.gaps) if verdict.gaps else "the evidence required by the statement"
    return f"Implement and document: {req.statement} Address: {gaps}."


def report_digest(report: AuditReport, max_chars: int = 9_000) -> str:
    reqs = {r.id: r for r in report.requirements}
    ev = {e.id: e for e in report.evidence}
    lines = [f"Target: {report.target}", f"Policies: {', '.join(report.policies)}"]
    if report.risk:
        lines.append(f"Risk tier: {report.risk.level.value} ({'; '.join(report.risk.triggers)}). {report.risk.rationale}")
    lines.append(f"Overall score: {report.overall_score:.0f}/100")
    lines.append("\nFindings:")
    for v in report.verdicts:
        r = reqs.get(v.requirement_id)
        title = r.title if r else v.requirement_id
        cites = ", ".join(f"{ev[i].path}:{ev[i].start_line}-{ev[i].end_line}" for i in v.evidence_ids if i in ev)
        lines.append(f"- {v.requirement_id} {title}: {v.status.value}"
                     + (f" | gaps: {'; '.join(v.gaps)}" if v.gaps else "")
                     + (f" | evidence: {cites}" if cites else ""))
    docs = [e for e in report.evidence if e.kind.value in ("doc", "model_card")][:4]
    if docs:
        lines.append("\nDocumentation excerpts:")
        for e in docs:
            lines.append(f"[{e.path}:{e.start_line}-{e.end_line}]\n{truncate(e.snippet, 1200)}")
    return truncate("\n".join(lines), max_chars)


def _template_artifact(kind: str, report: AuditReport) -> str:
    risk = report.risk.level.value if report.risk else "unknown"
    gaps = [g for v in report.verdicts if v.status in (Status.NON_COMPLIANT, Status.PARTIAL) for g in v.gaps]
    body = "\n".join(f"- [TODO] {g}" for g in gaps[:30]) or "- [TODO]"
    return (f"# {kind.replace('_', ' ').title()} (draft)\n\n> Generated from audit `{report.id}` of `{report.target}`. "
            f"Risk tier: **{risk}**.\n\n## Brief\n{ARTIFACT_BRIEFS[kind]}\n\n## Open gaps to address\n{body}\n")


class Remediator:
    def __init__(self, backend: LLMBackend | None = None, model: str | None = None):
        self.backend = backend
        self.model = model

    def run(self, req: Requirement, verdict: Verdict, evidence: list[Evidence] | None = None) -> str:
        """Return remediation text for a non-compliant/partial verdict (template fallback without LLM)."""
        if verdict.status not in (Status.NON_COMPLIANT, Status.PARTIAL, Status.NEEDS_REVIEW):
            return verdict.remediation
        if self.backend is None:
            return verdict.remediation or _template_remediation(req, verdict)
        ev_txt = "\n".join(f"- {e.path}:{e.start_line}-{e.end_line}" for e in (evidence or [])[:8]) or "- none"
        prompt = (f"Requirement {req.id}: {req.title}\nStatement: {req.statement}\nGuidance: {req.llm_guidance}\n"
                  f"Verdict: {verdict.status.value}. Rationale: {verdict.rationale}\nGaps: {'; '.join(verdict.gaps)}\n"
                  f"Relevant files:\n{ev_txt}\n\nReturn JSON {{\"remediation\": \"...\", \"steps\": [\"...\"]}}")
        try:
            raw = self.backend.complete_json(REMEDIATE_SYSTEM, prompt, REMEDIATE_SCHEMA, model=self.model)
        except Exception:  # noqa: BLE001
            return verdict.remediation or _template_remediation(req, verdict)
        text = str(raw.get("remediation") or "").strip()
        steps = [s for s in raw.get("steps") or [] if str(s).strip()]
        if steps:
            text += "\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
        return text or verdict.remediation or _template_remediation(req, verdict)


class ArtifactGenerator:
    def __init__(self, backend: LLMBackend | None = None, model: str | None = None):
        self.backend = backend
        self.model = model

    def draft_artifact(self, kind: str, report: AuditReport) -> str:
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"unknown artifact kind {kind!r}; expected one of {ARTIFACT_KINDS}")
        if self.backend is None:
            return _template_artifact(kind, report)
        prompt = (f"## Artefact to draft\n{kind}: {ARTIFACT_BRIEFS[kind]}\n\n## Audit findings\n"
                  f"{report_digest(report)}\n\nReturn JSON {{\"markdown\": \"...\"}}")
        try:
            raw = self.backend.complete_json(ARTIFACT_SYSTEM, prompt, ARTIFACT_SCHEMA, model=self.model)
        except Exception:  # noqa: BLE001
            return _template_artifact(kind, report)
        md = str(raw.get("markdown") or "").strip()
        return md or _template_artifact(kind, report)


def draft_artifact(kind: str, report: AuditReport, backend: LLMBackend | None = None,
                   model: str | None = None) -> str:
    return ArtifactGenerator(backend, model).draft_artifact(kind, report)
