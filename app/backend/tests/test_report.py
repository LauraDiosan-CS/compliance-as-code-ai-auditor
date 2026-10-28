import json

from ccauditor.models import Category, Requirement, Status, Verdict
from ccauditor.report.render import to_html, to_json, to_markdown, to_sarif
from ccauditor.report.scoring import build_scorecard

from helpers import make_report


def _r(rid: str, cat: Category, sev: str) -> Requirement:
    return Requirement(id=rid, policy_id="p", clause_ids=[], category=cat, title=rid, statement="s", severity=sev)


def _v(rid: str, status: Status) -> Verdict:
    return Verdict(requirement_id=rid, status=status, confidence=0.5, rationale="")


def test_scorecard_math():
    reqs = [
        _r("a", Category.SECURITY, "critical"),
        _r("b", Category.SECURITY, "low"),
        _r("c", Category.SECURITY, "medium"),
        _r("d", Category.SECURITY, "high"),
        _r("e", Category.TRANSPARENCY, "high"),
    ]
    verdicts = [
        _v("a", Status.COMPLIANT),
        _v("b", Status.PARTIAL),
        _v("c", Status.NEEDS_REVIEW),
        _v("d", Status.NOT_APPLICABLE),
        _v("e", Status.NON_COMPLIANT),
    ]
    cards, overall = build_scorecard(reqs, verdicts)
    sec = next(c for c in cards if c.category == Category.SECURITY)
    assert (sec.total, sec.compliant, sec.partial, sec.needs_review) == (3, 1, 1, 1)
    assert sec.score == 50.0  # (1 + 0.5) / 3
    tr = next(c for c in cards if c.category == Category.TRANSPARENCY)
    assert tr.score == 0.0 and tr.non_compliant == 1
    # weights: a4*1 + b1*0.5 + c2*0 + e3*0 = 4.5 / 10
    assert overall == 45.0
    assert build_scorecard([], []) == ([], 0.0)


def test_renderers(repo, requirements):
    report = make_report(repo, requirements)
    data = json.loads(to_json(report))
    assert data["id"] == "rep1" and len(data["verdicts"]) == 5

    md = to_markdown(report)
    assert "# Compliance Audit Report" in md
    assert "| Category | Score |" in md
    assert "[COMPLIANT] TP-REC-01" in md
    assert "app/main.py:L1-L" in md
    assert "```python" in md
    assert "## Needs human review" in md and "TP-TR-01" in md.split("## Needs human review")[1]

    html = to_html(report)
    assert html.startswith("<!doctype html>") and "TP-REC-01" in html


def test_sarif_structure(repo, requirements):
    report = make_report(repo, requirements)
    sarif = json.loads(to_sarif(report))
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    run = sarif["runs"][0]
    rules = run["tool"]["driver"]["rules"]
    assert [r["id"] for r in rules] == [r.id for r in requirements]
    assert all("category" in r["properties"] and "clause_ids" in r["properties"] for r in rules)
    levels = {res["ruleId"]: res["level"] for res in run["results"]}
    assert levels == {"TP-HO-01": "warning", "TP-TR-01": "note", "TP-SEC-01": "error"}
    for res in run["results"]:
        assert rules[res["ruleIndex"]]["id"] == res["ruleId"]
        loc = res["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"]
        assert loc["region"]["startLine"] >= 1
        assert res["message"]["text"]
    no_ev = next(r for r in run["results"] if r["ruleId"] == "TP-SEC-01")
    assert no_ev["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "README.md"
