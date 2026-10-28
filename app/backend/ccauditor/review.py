"""Human-in-the-loop: apply reviewer decisions to an existing audit report."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ccauditor.models import AuditReport, Status
from ccauditor.report.scoring import build_scorecard


class Review(BaseModel):
    requirement_id: str
    status: Status
    reviewer: str
    justification: str = ""


def apply_reviews(report: AuditReport, reviews: list[Review | dict[str, Any]]) -> AuditReport:
    """Return a copy of `report` with human overrides applied and the scorecard recomputed.

    Unknown requirement ids raise KeyError so typos are not silently ignored.
    """
    report = report.model_copy(deep=True)
    by_req = {v.requirement_id: v for v in report.verdicts}
    applied: list[dict[str, Any]] = []
    for raw in reviews:
        r = raw if isinstance(raw, Review) else Review.model_validate(raw)
        v = by_req.get(r.requirement_id)
        if v is None:
            raise KeyError(f"No verdict for requirement {r.requirement_id!r} in report {report.id}")
        previous = v.status
        v.status = r.status
        v.method = "human"
        v.confidence = 1.0
        v.verified = True
        note = f"Human review by {r.reviewer}: {previous.value} -> {r.status.value}."
        if r.justification:
            note += f" {r.justification}"
        v.rationale = f"{v.rationale}\n\n{note}".strip()
        if r.status == Status.COMPLIANT:
            v.gaps = []
        applied.append({"requirement_id": r.requirement_id, "from": previous.value, "to": r.status.value,
                        "reviewer": r.reviewer})
    report.scorecard, report.overall_score = build_scorecard(report.requirements, report.verdicts)
    report.stats = {**report.stats, "human_reviews": report.stats.get("human_reviews", []) + applied}
    return report
