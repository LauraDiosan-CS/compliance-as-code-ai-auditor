"""BM25 retrieval over evidence snippets, boosted by matching signals."""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from ccauditor.evidence.files import read_lines  # re-exported for convenience
from ccauditor.models import Evidence, EvidenceIndex, EvidenceKind

__all__ = ["Retriever", "tokenize", "read_lines"]

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*|\d+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "be", "on", "with", "by",
    "this", "that", "it", "as", "at", "from", "self", "def", "return", "import", "none", "true", "false",
}
SIGNAL_BOOST = 1.5
_GENERIC_SIGNAL_PARTS = {"call", "field", "config"}


def _signal_terms(signal: str) -> set[str]:
    return set(signal.split("_")) - _GENERIC_SIGNAL_PARTS


def tokenize(text: str) -> list[str]:
    """Lowercased tokens, splitting camelCase and snake_case; keeps the joined form too."""
    tokens: list[str] = []
    for raw in re.split(r"[^A-Za-z0-9_]+", text):
        if not raw:
            continue
        parts = [p for chunk in raw.split("_") for p in _CAMEL.sub(" ", chunk).split()]
        for p in parts:
            for w in _WORD.findall(p):
                w = w.lower()
                if len(w) > 1 and w not in _STOP:
                    tokens.append(w)
        if len(parts) > 1:
            tokens.append(raw.lower())
    return tokens


class Retriever:
    def __init__(self, index: EvidenceIndex) -> None:
        self.index = index
        self.items = index.items
        self._by_id = {e.id: e for e in self.items}
        corpus = [tokenize(f"{e.path} {e.snippet}") or ["_empty_"] for e in self.items]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def get(self, evidence_id: str) -> Evidence | None:
        return self._by_id.get(evidence_id)

    def search(self, query: str, k: int = 8, kinds: list[EvidenceKind] | None = None) -> list[Evidence]:
        if not self._bm25 or not query.strip():
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        qset = set(q)
        kind_set = {EvidenceKind(k_) for k_ in kinds} if kinds else None
        ranked: list[tuple[float, Evidence]] = []
        for score, e in zip(scores, self.items):
            if kind_set and e.kind not in kind_set:
                continue
            signals = [s for s in e.signal.split(",") if s]
            if any(qset & _signal_terms(s) for s in signals):
                score = score * SIGNAL_BOOST + 0.5
            if score <= 0:
                continue
            ranked.append((float(score), e))
        ranked.sort(key=lambda t: (-t[0], t[1].path, t[1].start_line))
        return [e.model_copy(update={"score": round(s, 4)}) for s, e in ranked[:k]]
