"""Helpers shared by the agents: evidence rendering, enum coercion, text utilities."""

from __future__ import annotations

import re
from typing import Iterable

from ..models import Category, Evidence, Requirement, RiskLevel, Status

STOPWORDS = set(
    """a an the and or of to in on for with by from is are be been being shall must should may can
    that this these those it its as at into each any all such which who whom whose where when what
    system systems provider providers deployer deployers ai artificial intelligence high risk ensure ensures
    appropriate relevant including include includes other than not no nor so if then there their they
    them per under within without between also has have had do does done will would could""".split()
)


def keywords(text: str, limit: int = 8) -> list[str]:
    """Cheap, LLM-free keyword extraction (order of first appearance, stopwords removed)."""
    seen: list[str] = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text.lower()):
        if w in STOPWORDS or w in seen:
            continue
        seen.append(w)
        if len(seen) >= limit:
            break
    return seen


def coerce_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        v = value.strip().lower().replace("-", "_").replace(" ", "_")
        for m in enum_cls:
            if m.value == v or m.name.lower() == v:
                return m
    return default


def coerce_status(value, default: Status = Status.NEEDS_REVIEW) -> Status:
    return coerce_enum(Status, value, default)


def coerce_category(value) -> Category:
    return coerce_enum(Category, value, Category.OTHER)


def coerce_risk(value) -> RiskLevel:
    return coerce_enum(RiskLevel, value, RiskLevel.UNKNOWN)


def clamp01(x, default: float = 0.5) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    if v > 1.0 and v <= 100.0:  # model answered in percent
        v = v / 100.0
    return max(0.0, min(1.0, v))


def str_list(x) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    return [str(i) for i in x if str(i).strip()]


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n... [truncated]"


def render_evidence(items: Iterable[Evidence], aliases: dict[str, str], snippet_chars: int = 1500) -> str:
    """Render evidence for a prompt. ``aliases`` maps alias (E1..) -> evidence id."""
    rev = {v: k for k, v in aliases.items()}
    blocks = []
    for ev in items:
        alias = rev.get(ev.id, ev.id)
        blocks.append(
            f"[{alias}] kind={ev.kind.value} file={ev.path} lines={ev.start_line}-{ev.end_line}"
            + (f" signal={ev.signal}" if ev.signal else "")
            + f"\n<<<\n{truncate(ev.snippet, snippet_chars)}\n>>>"
        )
    return "\n\n".join(blocks) if blocks else "(no evidence was found in the repository)"


def make_aliases(items: Iterable[Evidence]) -> dict[str, str]:
    """Short aliases (E1, E2, ...) are far less error-prone for the model than hash ids."""
    return {f"E{i + 1}": ev.id for i, ev in enumerate(items)}


def resolve_ids(raw_ids, aliases: dict[str, str]) -> list[str]:
    """Map aliases back to evidence ids. Unknown values are kept verbatim so the Verifier can drop them."""
    out: list[str] = []
    real = set(aliases.values())
    for r in str_list(raw_ids):
        r = r.strip().strip("[]")
        rid = aliases.get(r) or aliases.get(r.upper()) or (r if r in real else r)
        if rid not in out:
            out.append(rid)
    return out


def requirement_block(req: Requirement, clause_texts: dict[str, str] | None = None) -> str:
    lines = [
        f"Requirement {req.id} [{req.category.value}, severity={req.severity}]: {req.title}",
        f"Statement: {req.statement}",
    ]
    if req.llm_guidance:
        lines.append(f"Guidance for the auditor: {req.llm_guidance}")
    if req.checks:
        lines.append("Deterministic checks defined: " + "; ".join(
            c.description or f"{c.type} {c.pattern or c.path or ','.join(c.globs)} expect={c.expect}"
            for c in req.checks))
    if clause_texts:
        for cid in req.clause_ids:
            if cid in clause_texts:
                lines.append(f"Source clause {cid}: {truncate(clause_texts[cid], 1500)}")
    return "\n".join(lines)
