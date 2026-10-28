"""EvidenceScout: gathers the most relevant evidence for one requirement (LLM-free)."""

from __future__ import annotations

from typing import Any

from ..models import Evidence, EvidenceKind, Requirement, Verdict
from .common import keywords

DEFAULT_MAX_CHARS = 12_000
DEFAULT_MAX_ITEMS = 14
SNIPPET_CAP = 1_500

# category -> extra retrieval hints (cheap domain expansion, no LLM)
CATEGORY_HINTS: dict[str, list[str]] = {
    "record_keeping": ["logging logger audit log timestamp", "log prediction input output"],
    "transparency": ["disclose users interacting with AI notice", "chatbot disclaimer generated content label"],
    "human_oversight": ["human review override approve manual", "human in the loop escalation"],
    "data_governance": ["dataset data quality bias training data", "data validation schema preprocessing"],
    "technical_documentation": ["model card documentation architecture intended purpose", "README limitations"],
    "accuracy_robustness": ["evaluation accuracy metrics test", "robustness monitoring drift fallback"],
    "security": ["authentication secret encryption access control", "rate limit input validation tls"],
    "data_retention": ["retention delete purge ttl expire", "personal data storage period"],
    "risk_classification": ["intended purpose use case users", "risk assessment classification"],
}


class EvidenceScout:
    def __init__(self, retriever: Any, index_by_id: dict[str, Evidence] | None = None, k: int = 6,
                 max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS):
        self.retriever = retriever
        self.by_id = index_by_id if index_by_id is not None else {
            e.id: e for e in getattr(getattr(retriever, "index", None), "items", []) or []}
        self.k = k
        self.max_chars = max_chars
        self.max_items = max_items

    def queries(self, req: Requirement) -> list[str]:
        qs: list[str] = [q for q in req.evidence_queries if q.strip()]
        kw = keywords(f"{req.title} {req.statement}", limit=8)
        if kw:
            qs.append(" ".join(kw))
        qs.extend(CATEGORY_HINTS.get(req.category.value, [])[:1])
        return list(dict.fromkeys(qs))

    def run(self, req: Requirement, det_verdict: Verdict | None = None,
            kinds: list[EvidenceKind] | None = None) -> list[Evidence]:
        scored: dict[str, Evidence] = {}
        # 1) evidence cited by the deterministic engine comes first (it is what the rules matched)
        pinned: list[str] = []
        if det_verdict is not None:
            for eid in det_verdict.evidence_ids:
                ev = self.by_id.get(eid)
                if ev is not None and eid not in scored:
                    scored[eid] = ev.model_copy(update={"score": max(ev.score, 1e6)})
                    pinned.append(eid)
        # 2) retrieval, max score per item across queries; reciprocal-rank bonus favours items found by many queries
        bonus: dict[str, float] = {}
        for q in self.queries(req):
            try:
                hits = self.retriever.search(q, k=self.k, kinds=kinds)
            except TypeError:
                hits = self.retriever.search(q, self.k)
            for rank, ev in enumerate(hits):
                bonus[ev.id] = bonus.get(ev.id, 0.0) + 1.0 / (rank + 1)
                prev = scored.get(ev.id)
                if prev is None or ev.score > prev.score:
                    if ev.id not in pinned:
                        scored[ev.id] = ev
        ranked = sorted(scored.values(),
                        key=lambda e: (-(e.score + bonus.get(e.id, 0.0)), e.path, e.start_line))
        # 3) cap: number of items and total characters
        out: list[Evidence] = []
        total = 0
        for ev in ranked:
            if len(out) >= self.max_items:
                break
            snippet = ev.snippet if len(ev.snippet) <= SNIPPET_CAP else ev.snippet[:SNIPPET_CAP]
            if total + len(snippet) > self.max_chars and out:
                continue
            total += len(snippet)
            orig = self.by_id.get(ev.id)
            base = ev if orig is None else orig.model_copy(update={"score": ev.score if ev.id not in pinned else orig.score})
            out.append(base if snippet == base.snippet else base.model_copy(update={"snippet": snippet}))
        return out
