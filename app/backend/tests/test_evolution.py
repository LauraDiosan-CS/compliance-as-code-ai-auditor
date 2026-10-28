from ccauditor.models import AuditReport, Status, Verdict
from ccauditor.policies.evolution import affected_reports, diff_policies
from ccauditor.policies.loader import load_policy

from conftest import POLICIES


def test_diff_policies(requirements):
    old = load_policy(POLICIES / "test-policy.md")
    new = load_policy(POLICIES / "test-policy-v2.md")
    diff = diff_policies(old, new, requirements)
    added = {c["id"] for c in diff["added"]}
    removed = {c["id"] for c in diff["removed"]}
    modified = {c["id"] for c in diff["modified"]}
    assert added == {"test-policy/Art.50", "test-policy/Art.50(1)"}
    assert removed == {"test-policy/Art.14", "test-policy/Art.14(1)"}
    assert modified == {"test-policy/Art.12(1)"}
    assert "test-policy/Art.12(2)" in diff["unchanged"]
    affected = {a["requirement_id"]: a for a in diff["affected_requirements"]}
    assert set(affected) == {"TP-REC-01", "TP-HO-01", "TP-TR-01"}
    # TP-HO-01 cites parent Art.14 whose child was removed too
    assert any("removed" in r for r in affected["TP-HO-01"]["reasons"])
    assert diff["modified"][0]["similarity"] < 1


def test_affected_reports(requirements):
    old = load_policy(POLICIES / "test-policy.md")
    new = load_policy(POLICIES / "test-policy-v2.md")
    diff = diff_policies(old, new, requirements)
    report = AuditReport(
        id="r1", target="x", policies=["test-policy"], mode="deterministic",
        requirements=requirements,
        verdicts=[Verdict(requirement_id="TP-REC-01", status=Status.COMPLIANT, confidence=0.9, rationale="ok")],
        evidence=[],
    )
    out = affected_reports(diff, [report])
    assert out[0]["report_id"] == "r1"
    assert "TP-REC-01" in out[0]["requirements"]
    assert out[0]["previous_statuses"]["TP-REC-01"] == "compliant"
