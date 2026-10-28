"""Verifier: anti-hallucination checks on verdicts.

Deterministic pass (always): drop cited ids that were not in the evidence given to the judge;
a compliant/partial verdict with no valid citation is downgraded to needs_review.
Optional LLM pass: checks that each cited snippet actually supports the claim.
"""

from __future__ import annotations

from ..llm.backend import LLMBackend
from ..models import Evidence, Requirement, Status, Verdict
from .common import make_aliases, render_evidence, resolve_ids, str_list

VERIFY_SYSTEM = """You are Verifier, a skeptical second auditor. You check whether cited evidence excerpts actually support
a compliance claim. You must not use outside knowledge about the repository: only the excerpts shown.
For each cited excerpt decide whether it supports the claim. Answer with a single JSON object only."""

VERIFY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "unsupported_ids": {"type": "array", "items": {"type": "string"}},
        "comment": {"type": "string"},
    },
    "required": ["supported", "unsupported_ids"],
}

POSITIVE = (Status.COMPLIANT, Status.PARTIAL)


class Verifier:
    def __init__(self, backend: LLMBackend | None = None, use_llm: bool = False, model: str | None = None):
        self.backend = backend
        self.use_llm = use_llm and backend is not None
        self.model = model

    def check(self, verdict: Verdict, valid_ids: set[str] | dict[str, Evidence],
              require_evidence: bool = True) -> Verdict:
        """Deterministic verification. ``valid_ids`` = ids of the evidence actually provided.

        ``require_evidence=False`` is used for rule-engine verdicts, where e.g. an ``expect: absent``
        check legitimately passes without citing anything.
        """
        valid = set(valid_ids.keys()) if isinstance(valid_ids, dict) else set(valid_ids)
        v = verdict.model_copy(deep=True)
        kept = [i for i in v.evidence_ids if i in valid]
        dropped = [i for i in v.evidence_ids if i not in valid]
        v.evidence_ids = list(dict.fromkeys(kept))
        notes = []
        if dropped:
            notes.append(f"Verifier removed {len(dropped)} citation(s) not present in the evidence set: "
                         + ", ".join(dropped[:5]))
            v.confidence = round(v.confidence * 0.8, 3)
        if require_evidence and v.status in POSITIVE and not v.evidence_ids:
            notes.append(f"Verifier: '{v.status.value}' claimed without any valid evidence citation; "
                         "downgraded to needs_review (no hallucinated compliance).")
            v.status = Status.NEEDS_REVIEW
            v.confidence = round(min(v.confidence, 0.4), 3)
        if notes:
            v.rationale = (v.rationale + "\n" + "\n".join(notes)).strip()
        v.verified = True
        return v

    def llm_check(self, req: Requirement, verdict: Verdict, evidence: dict[str, Evidence]) -> Verdict:
        """Optional claim-support check of each cited snippet (only for positive verdicts)."""
        if not self.use_llm or verdict.status not in POSITIVE or not verdict.evidence_ids:
            return verdict
        cited = [evidence[i] for i in verdict.evidence_ids if i in evidence]
        aliases = make_aliases(cited)
        prompt = (
            f"Requirement {req.id}: {req.statement}\n\n"
            f"Claim: status={verdict.status.value}. Rationale: {verdict.rationale}\n\n"
            f"Cited excerpts:\n{render_evidence(cited, aliases)}\n\n"
            "Return JSON {\"supported\": true|false, \"unsupported_ids\": [ids of excerpts that do NOT support "
            "the claim], \"comment\": \"one sentence\"}. supported=false if the excerpts together do not support "
            "the claimed status."
        )
        try:
            raw = self.backend.complete_json(VERIFY_SYSTEM, prompt, VERIFY_SCHEMA, model=self.model)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return verdict
        v = verdict.model_copy(deep=True)
        bad = set(resolve_ids(str_list(raw.get("unsupported_ids")), aliases))
        if bad:
            v.evidence_ids = [i for i in v.evidence_ids if i not in bad]
        comment = str(raw.get("comment") or "").strip()
        if raw.get("supported") is False or not v.evidence_ids:
            v.status = Status.NEEDS_REVIEW
            v.confidence = round(min(v.confidence, 0.5), 3)
            v.rationale += f"\nVerifier (LLM): cited evidence does not support the claim. {comment}".rstrip()
            v.evidence_ids = list(verdict.evidence_ids)  # keep them visible for the human reviewer
        elif comment:
            v.rationale += f"\nVerifier (LLM): {comment}"
        return v

    def run(self, req: Requirement, verdict: Verdict, evidence: dict[str, Evidence]) -> Verdict:
        v = self.check(verdict, evidence)
        return self.llm_check(req, v, evidence)
