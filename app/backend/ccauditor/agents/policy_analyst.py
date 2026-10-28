"""PolicyAnalyst: decomposes policy clauses into verifiable Requirements (used when no curated YAML exists)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from ..llm.backend import LLMBackend
from ..models import Category, Clause, Policy, Requirement, RiskLevel
from .common import coerce_category, coerce_risk, str_list, truncate

ANALYST_SYSTEM = """You are PolicyAnalyst, a compliance engineer who turns legal/policy text into verifiable requirements
for auditing a software repository of an AI application.
For each clause that imposes an obligation that can be checked in code, configuration, infrastructure or documentation,
write one or more requirements. Skip purely definitional, procedural or authority-facing clauses (return nothing for them).
Each requirement must be:
- atomic and testable: a normative statement about the repository ("The system logs ...", "The README documents ...");
- mapped to the clause ids it derives from (use ONLY the clause ids given);
- given a category from this list: risk_classification, transparency, record_keeping, human_oversight, data_governance,
  technical_documentation, accuracy_robustness, security, data_retention, other;
- given 2-5 short evidence_queries (keywords/code identifiers a search engine would match in a repository);
- given llm_guidance: what an auditor should look for and what counts as compliant vs not;
- given severity (critical, high, medium, low) and applies_to: risk tiers among prohibited, high, limited, minimal
  (EU AI Act high-risk obligations -> ["high"]; transparency duties -> ["high","limited"]; general/internal policies ->
  ["high","limited","minimal"]).
Answer with a single JSON object only."""

ANALYST_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_ids": {"type": "array", "items": {"type": "string"}},
                    "category": {"type": "string", "enum": [c.value for c in Category]},
                    "title": {"type": "string"},
                    "statement": {"type": "string"},
                    "applies_to": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "evidence_queries": {"type": "array", "items": {"type": "string"}},
                    "llm_guidance": {"type": "string"},
                },
                "required": ["clause_ids", "category", "title", "statement"],
            },
        }
    },
    "required": ["requirements"],
}

_CAT_CODE = {
    Category.RISK_CLASSIFICATION: "RSK", Category.TRANSPARENCY: "TRA", Category.RECORD_KEEPING: "REC",
    Category.HUMAN_OVERSIGHT: "HUM", Category.DATA_GOVERNANCE: "DAT", Category.TECHNICAL_DOCUMENTATION: "DOC",
    Category.ACCURACY_ROBUSTNESS: "ACC", Category.SECURITY: "SEC", Category.DATA_RETENTION: "RET",
    Category.OTHER: "OTH",
}


def leaf_clauses(policy: Policy) -> list[Clause]:
    """Clauses that are not parents of other clauses (parents' text is usually just a heading)."""
    parents = {c.parent_id for c in policy.clauses if c.parent_id}
    return [c for c in policy.clauses if c.id not in parents and c.text.strip()]


def _prefix(policy_id: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", policy_id)
    return "".join(w[0] for w in words).upper()[:4] or "POL"


class PolicyAnalyst:
    def __init__(self, backend: LLMBackend, model: str | None = None, batch_size: int = 6,
                 batch_chars: int = 9_000):
        self.backend = backend
        self.model = model
        self.batch_size = batch_size
        self.batch_chars = batch_chars

    def batches(self, policy: Policy) -> list[list[Clause]]:
        out: list[list[Clause]] = []
        cur: list[Clause] = []
        size = 0
        for c in leaf_clauses(policy):
            ln = min(len(c.text), 2500)
            if cur and (len(cur) >= self.batch_size or size + ln > self.batch_chars):
                out.append(cur)
                cur, size = [], 0
            cur.append(c)
            size += ln
        if cur:
            out.append(cur)
        return out

    def _prompt(self, policy: Policy, batch: list[Clause]) -> str:
        titles = {c.id: c.title for c in policy.clauses}
        blocks = []
        for c in batch:
            parent = f" (in {c.parent_id}: {titles.get(c.parent_id, '')})" if c.parent_id else ""
            blocks.append(f"[{c.id}] {c.title}{parent}\n{truncate(c.text, 2500)}")
        return (
            f"Policy: {policy.name} (id={policy.id}, kind={policy.kind})\n\n## Clauses\n" + "\n\n".join(blocks)
            + "\n\n## Task\nReturn JSON {\"requirements\": [{\"clause_ids\": [...], \"category\": \"...\", "
            "\"title\": \"...\", \"statement\": \"...\", \"applies_to\": [...], \"severity\": \"...\", "
            "\"evidence_queries\": [...], \"llm_guidance\": \"...\"}]}"
        )

    def _parse(self, policy: Policy, batch: list[Clause], raw: dict) -> list[dict]:
        valid = {c.id for c in batch}
        out = []
        for r in raw.get("requirements") or []:
            if not isinstance(r, dict) or not str(r.get("statement") or "").strip():
                continue
            cids = [c for c in str_list(r.get("clause_ids")) if c in valid] or [batch[0].id]
            applies = [lv for lv in (coerce_risk(x) for x in str_list(r.get("applies_to"))) if lv != RiskLevel.UNKNOWN]
            sev = str(r.get("severity") or "medium").lower()
            out.append(dict(
                policy_id=policy.id,
                clause_ids=cids,
                category=coerce_category(r.get("category")),
                title=str(r.get("title") or "").strip()[:120] or str(r["statement"])[:60],
                statement=str(r["statement"]).strip(),
                applies_to=applies or [RiskLevel.HIGH, RiskLevel.LIMITED, RiskLevel.MINIMAL],
                severity=sev if sev in ("critical", "high", "medium", "low") else "medium",
                evidence_queries=str_list(r.get("evidence_queries"))[:6],
                llm_guidance=str(r.get("llm_guidance") or "").strip(),
                checks=[],
            ))
        return out

    def run(self, policy: Policy, concurrency: int | None = None) -> list[Requirement]:
        batches = self.batches(policy)
        if not batches:
            return []

        def work(batch: list[Clause]) -> list[dict]:
            try:
                raw = self.backend.complete_json(ANALYST_SYSTEM, self._prompt(policy, batch), ANALYST_SCHEMA,
                                                 model=self.model)
            except Exception:  # noqa: BLE001 - skip a failed batch rather than abort
                return []
            return self._parse(policy, batch, raw)

        workers = max(1, concurrency or getattr(self.backend, "concurrency", 1))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(work, batches))
        prefix = _prefix(policy.id)
        counters: dict[Category, int] = {}
        reqs: list[Requirement] = []
        for items in results:
            for d in items:
                cat = d["category"]
                counters[cat] = counters.get(cat, 0) + 1
                reqs.append(Requirement(id=f"{prefix}-{_CAT_CODE[cat]}-{counters[cat]:02d}", **d))
        return reqs
