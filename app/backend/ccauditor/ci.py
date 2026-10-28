"""CI helpers: changed files, regression detection against a baseline report, fail policy."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ccauditor.models import AuditReport, Status

SEVERITIES = ("critical", "high", "medium", "low")
# Higher rank = better compliance. NOT_APPLICABLE is not ranked (never a regression).
STATUS_RANK = {
    Status.NON_COMPLIANT: 0,
    Status.NEEDS_REVIEW: 1,
    Status.PARTIAL: 2,
    Status.COMPLIANT: 3,
}


def severities_at_or_above(level: str) -> tuple[str, ...]:
    """'high' -> ('critical', 'high')."""
    level = level.lower()
    if level not in SEVERITIES:
        raise ValueError(f"unknown severity {level!r}; expected one of {SEVERITIES}")
    return SEVERITIES[: SEVERITIES.index(level) + 1]


def changed_files(repo_root: str | Path, base_ref: str) -> list[str]:
    """Files changed between base_ref and the working tree (git diff --name-only)."""
    cmd = ["git", "-C", str(repo_root), "diff", "--name-only", base_ref]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _cited_paths(report: AuditReport, requirement_id: str) -> set[str]:
    ev = {e.id: e for e in report.evidence}
    for v in report.verdicts:
        if v.requirement_id == requirement_id:
            return {ev[i].path for i in v.evidence_ids if i in ev}
    return set()


def compare_reports(
    baseline: AuditReport, current: AuditReport, changed: list[str] | None = None
) -> dict[str, Any]:
    """Diff two reports requirement by requirement.

    Returns {"regressions", "improvements", "unchanged", "new_requirements", "removed_requirements",
    "score_delta", "baseline_score", "current_score"}. Each regression/improvement entry has
    requirement_id, title, severity, category, from, to, lost_evidence (paths cited before but not now)
    and touches_changed_files (when `changed` is given).
    """
    base_v = {v.requirement_id: v for v in baseline.verdicts}
    cur_v = {v.requirement_id: v for v in current.verdicts}
    reqs = {r.id: r for r in baseline.requirements}
    reqs.update({r.id: r for r in current.requirements})
    changed_set = set(changed or [])

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for rid in sorted(set(base_v) & set(cur_v)):
        b, c = base_v[rid].status, cur_v[rid].status
        if b not in STATUS_RANK or c not in STATUS_RANK:
            unchanged.append(rid)
            continue
        delta = STATUS_RANK[c] - STATUS_RANK[b]
        if delta == 0:
            unchanged.append(rid)
            continue
        req = reqs[rid]
        before, after = _cited_paths(baseline, rid), _cited_paths(current, rid)
        entry: dict[str, Any] = {
            "requirement_id": rid,
            "title": req.title,
            "severity": req.severity,
            "category": req.category.value,
            "from": b.value,
            "to": c.value,
            "lost_evidence": sorted(before - after),
            "new_evidence": sorted(after - before),
            "gaps": cur_v[rid].gaps,
        }
        if changed is not None:
            entry["touches_changed_files"] = bool((before | after) & changed_set)
        (regressions if delta < 0 else improvements).append(entry)

    return {
        "baseline_id": baseline.id,
        "current_id": current.id,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "new_requirements": sorted(set(cur_v) - set(base_v)),
        "removed_requirements": sorted(set(base_v) - set(cur_v)),
        "baseline_score": baseline.overall_score,
        "current_score": current.overall_score,
        "score_delta": round(current.overall_score - baseline.overall_score, 1),
        "changed_files": sorted(changed_set) if changed is not None else None,
    }


def should_fail(diff: dict[str, Any], fail_on: tuple[str, ...] | list[str] = ("critical", "high")) -> bool:
    """True when any regression has a severity in fail_on."""
    return any(r["severity"] in fail_on for r in diff.get("regressions", []))


def open_gaps(report: AuditReport, fail_on: tuple[str, ...] | list[str] = ("critical", "high")) -> list[dict[str, Any]]:
    """Non-compliant requirements of the given severities (used when no baseline exists)."""
    reqs = {r.id: r for r in report.requirements}
    out = []
    for v in report.verdicts:
        req = reqs.get(v.requirement_id)
        if req and v.status == Status.NON_COMPLIANT and req.severity in fail_on:
            out.append({"requirement_id": req.id, "title": req.title, "severity": req.severity, "gaps": v.gaps})
    return out
