from __future__ import annotations

from ccauditor.evidence.collector import collect
from ccauditor.models import AuditReport, Requirement
from ccauditor.report.scoring import build_scorecard
from ccauditor.rules.engine import evaluate_all


def make_report(repo, requirements: list[Requirement], report_id: str = "rep1") -> AuditReport:
    index = collect(repo)
    verdicts = evaluate_all(requirements, repo, index)
    cited = {i for v in verdicts for i in v.evidence_ids}
    scorecard, overall = build_scorecard(requirements, verdicts)
    return AuditReport(
        id=report_id, target=str(repo), policies=["test-policy"], mode="deterministic",
        requirements=requirements, verdicts=verdicts,
        evidence=[e for e in index.items if e.id in cited],
        scorecard=scorecard, overall_score=overall,
    )
