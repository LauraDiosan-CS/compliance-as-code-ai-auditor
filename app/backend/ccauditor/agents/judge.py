"""ComplianceJudge: decides a requirement's status from retrieved evidence, citing evidence ids."""

from __future__ import annotations

from ..llm.backend import LLMBackend
from ..models import Evidence, Requirement, Status, Verdict
from .common import (
    clamp01,
    coerce_status,
    make_aliases,
    render_evidence,
    requirement_block,
    resolve_ids,
    str_list,
)

JUDGE_SYSTEM = """You are ComplianceJudge, a meticulous compliance auditor for AI systems (EU AI Act, GDPR, internal policies).
You assess ONE requirement against evidence excerpts taken from a software repository.

Rules you must follow:
1. Base your decision ONLY on the evidence excerpts provided. Each excerpt has an id in square brackets, e.g. [E3].
2. Cite evidence ONLY by the ids provided (e.g. "E3"). Never invent ids, files or line numbers.
3. Never assume compliance. Absence of evidence is not evidence of compliance.
4. If no provided evidence supports compliance, status MUST be "non_compliant" (the evidence set clearly lacks what is required) or "needs_review" (you cannot tell).
5. "compliant": the evidence clearly and fully satisfies the statement. "partial": some but not all elements are satisfied.
   "needs_review": the evidence is genuinely ambiguous or conflicting and a human must decide.
6. confidence is your probability (0..1) that your status is correct. Be calibrated; use < 0.6 when unsure.
7. gaps: concrete missing elements (short phrases). remediation: concrete, actionable fix for the repository (files/code/docs to add).
8. A deterministic rule-engine result may be provided as a hint; it can be wrong (regexes are shallow). Weigh it, but judge the evidence.
Answer with a single JSON object only."""

JUDGE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["compliant", "partial", "non_compliant", "needs_review"]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "remediation": {"type": "string"},
    },
    "required": ["status", "confidence", "rationale", "evidence_ids"],
}


class ComplianceJudge:
    def __init__(self, backend: LLMBackend, model: str | None = None):
        self.backend = backend
        self.model = model

    def build_prompt(self, req: Requirement, evidence: list[Evidence], aliases: dict[str, str],
                     det_verdict: Verdict | None = None, clause_texts: dict[str, str] | None = None) -> str:
        parts = ["## Requirement", requirement_block(req, clause_texts), "", "## Evidence excerpts",
                 render_evidence(evidence, aliases)]
        if det_verdict is not None:
            rev = {v: k for k, v in aliases.items()}
            cited = ", ".join(rev.get(i, i) for i in det_verdict.evidence_ids) or "none"
            parts += ["", "## Deterministic rule-engine result (hint)",
                      f"status={det_verdict.status.value} confidence={det_verdict.confidence:.2f} cited={cited}",
                      f"rationale: {det_verdict.rationale}"]
        parts += ["", "## Task",
                  "Return JSON: {\"status\": \"compliant|partial|non_compliant|needs_review\", \"confidence\": 0..1, "
                  "\"rationale\": \"2-4 sentences referencing evidence ids\", \"evidence_ids\": [\"E1\", ...], "
                  "\"gaps\": [\"...\"], \"remediation\": \"...\"}"]
        return "\n".join(parts)

    def run(self, req: Requirement, evidence: list[Evidence], det_verdict: Verdict | None = None,
            clause_texts: dict[str, str] | None = None, method: str = "llm") -> Verdict:
        aliases = make_aliases(evidence)
        prompt = self.build_prompt(req, evidence, aliases, det_verdict, clause_texts)
        try:
            raw = self.backend.complete_json(JUDGE_SYSTEM, prompt, JUDGE_SCHEMA, model=self.model)
        except Exception as e:  # noqa: BLE001 - an LLM failure must not crash the audit
            return Verdict(requirement_id=req.id, status=Status.NEEDS_REVIEW, confidence=0.0,
                           rationale=f"LLM judge failed: {e}", method=method)  # type: ignore[arg-type]
        status = coerce_status(raw.get("status"))
        if status == Status.NOT_APPLICABLE:  # the judge is not allowed to decide applicability
            status = Status.NEEDS_REVIEW
        return Verdict(
            requirement_id=req.id,
            status=status,
            confidence=clamp01(raw.get("confidence"), 0.5),
            rationale=str(raw.get("rationale") or "").strip() or "(no rationale given)",
            evidence_ids=resolve_ids(raw.get("evidence_ids"), aliases),
            gaps=str_list(raw.get("gaps")),
            remediation=str(raw.get("remediation") or "").strip(),
            method=method,  # type: ignore[arg-type]
            verified=False,
        )
