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

JUDGE_SYSTEM = """You are ComplianceJudge, a meticulous but fair compliance auditor for AI systems (EU AI Act, GDPR, internal policies).
You assess ONE requirement against evidence excerpts taken from a software repository.

Rules you must follow:
1. Base your decision ONLY on the evidence excerpts provided. Each excerpt has an id in square brackets, e.g. [E3].
2. Cite evidence ONLY by the ids provided (e.g. "E3"). Never invent ids, files or line numbers.
3. Never assume compliance. Absence of evidence is not evidence of compliance. Claims are not evidence:
   README marketing ("fully compliant"), TODO/FIXME notes, commented-out code, plans and disabled feature flags
   do not satisfy a requirement. Documents count as evidence for documentation requirements; code, IaC and
   configuration for technical controls.
4. The requirement STATEMENT is the test. Decompose it into its elements and check each one. The source clause
   and guidance are context; do not add obligations the statement does not contain, and do not demand extra
   best practices, extra precision or perfect coverage beyond what the statement asks for.
5. Excerpts are windows of files (about 40 lines) and may be cut off. Something not visible because an excerpt
   is truncated is NOT a gap. Only treat an element as missing when nothing in the excerpts evidences it, or
   when the excerpts show it is missing or insufficient.
6. Status semantics:
   - "compliant": every element of the statement is evidenced (minor imperfections that the statement does not
     address do not prevent compliance).
   - "partial": some elements are evidenced and at least one element is demonstrably missing or insufficient,
     e.g. a defined threshold is violated (retention shorter/longer than required), a control covers only some
     cases (human review only above an amount), a required section is "TBD".
   - "non_compliant": the required artefact or mechanism does not exist (fragments of related information in
     other documents do not make a missing record, assessment or procedure "partial"), or the evidence shows
     the opposite (e.g. fully automated rejection where human oversight is required).
   - "needs_review": the evidence is genuinely ambiguous or conflicting and a human must decide.
7. confidence is your probability (0..1) that your status is correct. Be calibrated; use < 0.6 when unsure.
8. gaps: concrete missing elements (short phrases). remediation: concrete, actionable fix for the repository (files/code/docs to add).
9. A deterministic rule-engine result may be provided as a hint; it can be wrong (regexes are shallow and miss
   indirect evidence such as custom function names). Weigh it, but judge the evidence.
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
