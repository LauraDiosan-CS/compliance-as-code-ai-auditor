"""Category scorecard and severity-weighted overall score."""

from __future__ import annotations

from ccauditor.models import Category, CategoryScore, Requirement, Status, Verdict

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CREDIT = {Status.COMPLIANT: 1.0, Status.PARTIAL: 0.5}  # everything else earns 0


def build_scorecard(
    requirements: list[Requirement], verdicts: list[Verdict]
) -> tuple[list[CategoryScore], float]:
    """Return (per-category scores, overall score 0..100).

    Category score = (compliant + 0.5*partial) / applicable * 100, NOT_APPLICABLE excluded,
    NEEDS_REVIEW (and requirements without a verdict) count as 0 but are tracked.
    Overall = same credit, weighted by severity (critical 4, high 3, medium 2, low 1).
    """
    by_req = {v.requirement_id: v for v in verdicts}
    buckets: dict[Category, list[Status]] = {}
    weighted = 0.0
    weight_total = 0
    for req in requirements:
        v = by_req.get(req.id)
        status = v.status if v else Status.NEEDS_REVIEW
        if status == Status.NOT_APPLICABLE:
            continue
        buckets.setdefault(req.category, []).append(status)
        w = SEVERITY_WEIGHT.get(req.severity, 2)
        weighted += w * CREDIT.get(status, 0.0)
        weight_total += w

    scores: list[CategoryScore] = []
    for cat in Category:  # stable, enum order
        statuses = buckets.get(cat)
        if not statuses:
            continue
        c = statuses.count(Status.COMPLIANT)
        p = statuses.count(Status.PARTIAL)
        scores.append(
            CategoryScore(
                category=cat,
                total=len(statuses),
                compliant=c,
                partial=p,
                non_compliant=statuses.count(Status.NON_COMPLIANT),
                needs_review=statuses.count(Status.NEEDS_REVIEW),
                score=round((c + 0.5 * p) / len(statuses) * 100, 1),
            )
        )
    overall = round(weighted / weight_total * 100, 1) if weight_total else 0.0
    return scores, overall
