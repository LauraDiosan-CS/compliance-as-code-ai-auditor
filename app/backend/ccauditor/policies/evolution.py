"""Policy evolution: diff two versions of a policy and find impacted requirements / reports."""

from __future__ import annotations

import difflib
from typing import Any

from ccauditor.models import AuditReport, Clause, Policy, Requirement

# Clauses whose text similarity is below this ratio are reported as "modified".
MODIFIED_THRESHOLD = 0.999


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _related(clause_id: str, changed: set[str]) -> bool:
    """True if clause_id is changed, or is a parent/child (prefix relation) of a changed clause."""
    for c in changed:
        if clause_id == c:
            return True
        # child of a changed clause: "x/Art.12(1)" vs changed "x/Art.12"
        if clause_id.startswith(c + "(") or c.startswith(clause_id + "("):
            return True
    return False


def diff_policies(old: Policy, new: Policy, requirements: list[Requirement]) -> dict[str, Any]:
    """Compare two policy versions.

    Returns {"old_version", "new_version", "added", "removed", "modified", "unchanged",
    "affected_requirements": [{"requirement_id", "title", "clause_ids", "reasons"}]}.
    """
    old_by_id: dict[str, Clause] = {c.id: c for c in old.clauses}
    new_by_id: dict[str, Clause] = {c.id: c for c in new.clauses}

    added = [
        {"id": c.id, "title": c.title, "text": c.text} for cid, c in new_by_id.items() if cid not in old_by_id
    ]
    removed = [
        {"id": c.id, "title": c.title, "text": c.text} for cid, c in old_by_id.items() if cid not in new_by_id
    ]
    modified: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for cid, oc in old_by_id.items():
        nc = new_by_id.get(cid)
        if nc is None:
            continue
        old_txt = f"{oc.title}\n{oc.text}"
        new_txt = f"{nc.title}\n{nc.text}"
        sim = _similarity(old_txt, new_txt)
        if sim < MODIFIED_THRESHOLD:
            diff = list(
                difflib.unified_diff(
                    oc.text.splitlines(), nc.text.splitlines(), "old", "new", lineterm="", n=1
                )
            )
            modified.append(
                {
                    "id": cid,
                    "title": nc.title,
                    "similarity": round(sim, 3),
                    "diff": "\n".join(diff),
                }
            )
        else:
            unchanged.append(cid)

    change_kind = {c["id"]: "added" for c in added}
    change_kind.update({c["id"]: "removed" for c in removed})
    change_kind.update({c["id"]: "modified" for c in modified})
    changed = set(change_kind)

    affected: list[dict[str, Any]] = []
    for req in requirements:
        reasons: list[str] = []
        for cid in req.clause_ids:
            for ch in changed:
                if cid == ch:
                    reasons.append(f"{cid} {change_kind[ch]}")
                elif _related(cid, {ch}):
                    reasons.append(f"{cid} related to {change_kind[ch]} clause {ch}")
        if reasons:
            affected.append(
                {
                    "requirement_id": req.id,
                    "title": req.title,
                    "clause_ids": req.clause_ids,
                    "reasons": sorted(set(reasons)),
                }
            )

    return {
        "policy_id": new.id,
        "old_version": old.version,
        "new_version": new.version,
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
        "affected_requirements": affected,
    }


def affected_reports(diff: dict[str, Any], reports: list[AuditReport]) -> list[dict[str, Any]]:
    """Which previous audit reports contain verdicts that a policy change invalidates."""
    affected_ids = {a["requirement_id"] for a in diff.get("affected_requirements", [])}
    changed = {c["id"] for key in ("added", "removed", "modified") for c in diff.get(key, [])}
    out: list[dict[str, Any]] = []
    for rep in reports:
        hit: set[str] = set()
        for req in rep.requirements:
            if req.id in affected_ids or any(_related(cid, changed) for cid in req.clause_ids):
                hit.add(req.id)
        if hit:
            statuses = {v.requirement_id: v.status.value for v in rep.verdicts}
            out.append(
                {
                    "report_id": rep.id,
                    "target": rep.target,
                    "created_at": rep.created_at.isoformat(),
                    "requirements": sorted(hit),
                    "previous_statuses": {r: statuses.get(r) for r in sorted(hit)},
                    "needs_reaudit": True,
                }
            )
    return out
