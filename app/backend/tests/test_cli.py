import json

from typer.testing import CliRunner

from ccauditor import cli
from ccauditor.models import AuditReport

from conftest import POLICIES

runner = CliRunner()


def _audit_json(repo, tmp_path, name="report.json"):
    out = tmp_path / name
    res = runner.invoke(cli.app, [
        "audit", str(repo), "--policy", "test-policy", "--mode", "deterministic",
        "--requirements", str(POLICIES / "test-policy.yaml"), "--format", "json", "--out", str(out),
    ])
    assert res.exit_code == 0, res.output
    return out


def test_policies_command():
    res = runner.invoke(cli.app, ["policies", "--json"])
    assert res.exit_code == 0
    assert isinstance(json.loads(res.stdout), list)


def test_audit_formats(repo, tmp_path):
    out = _audit_json(repo, tmp_path)
    report = AuditReport.model_validate_json(out.read_text())
    assert len(report.verdicts) == 5
    cited = {i for v in report.verdicts for i in v.evidence_ids}
    assert cited <= {e.id for e in report.evidence}
    for fmt, marker in (("md", "# Compliance Audit Report"), ("sarif", '"version": "2.1.0"')):
        res = runner.invoke(cli.app, [
            "audit", str(repo), "-p", "test-policy", "-m", "deterministic",
            "-r", str(POLICIES / "test-policy.yaml"), "-f", fmt,
        ])
        assert res.exit_code == 0, res.output
        assert marker in res.stdout


def test_deterministic_fallback(repo):
    from ccauditor.policies.loader import load_requirements

    report = cli._deterministic_audit(str(repo), ["test-policy"],
                                      requirements_override=load_requirements(POLICIES / "test-policy.yaml"))
    assert report.mode == "deterministic" and report.overall_score > 0


def test_diff_policy_command():
    res = runner.invoke(cli.app, [
        "diff-policy", str(POLICIES / "test-policy.md"), str(POLICIES / "test-policy-v2.md"),
        "-r", str(POLICIES / "test-policy.yaml"), "--json",
    ])
    assert res.exit_code == 0, res.output
    diff = json.loads(res.stdout)
    assert {a["requirement_id"] for a in diff["affected_requirements"]} >= {"TP-REC-01"}
    text = runner.invoke(cli.app, ["diff-policy", str(POLICIES / "test-policy.md"), str(POLICIES / "test-policy-v2.md"),
                                   "-r", str(POLICIES / "test-policy.yaml")])
    assert "Modified clauses: 1" in text.stdout


def test_ci_command_regression(repo, tmp_path, monkeypatch):
    from ccauditor.policies.loader import load_requirements

    reqs = load_requirements(POLICIES / "test-policy.yaml")
    # make the CLI use the fixture requirements for policy "test-policy"
    monkeypatch.setattr(
        cli, "resolve_run_audit",
        lambda: lambda root, pids, **kw: cli._deterministic_audit(root, pids, requirements_override=reqs),
    )
    baseline = _audit_json(repo, tmp_path, "baseline.json")
    res = runner.invoke(cli.app, ["ci", str(repo), "--baseline", str(baseline), "--fail-on", "high"])
    assert res.exit_code == 0, res.output
    assert "CI result: PASS" in res.stdout

    main = repo / "app" / "main.py"
    main.write_text(main.read_text().replace("logger.info(", "print("))
    res = runner.invoke(cli.app, ["ci", str(repo), "--baseline", str(baseline), "--fail-on", "high"])
    assert res.exit_code == 1
    assert "REGRESSION [high] TP-REC-01" in res.stdout

    # without baseline: fails on open high/critical gaps (TP-SEC-01 is high + non_compliant)
    res = runner.invoke(cli.app, ["ci", str(repo), "-p", "test-policy", "--fail-on", "critical"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(cli.app, ["ci", str(repo), "-p", "test-policy", "--fail-on", "high"])
    assert res.exit_code == 1


def test_review_apply(repo, tmp_path):
    report_path = _audit_json(repo, tmp_path)
    reviews = tmp_path / "reviews.json"
    reviews.write_text(json.dumps([
        {"requirement_id": "TP-TR-01", "status": "compliant", "reviewer": "alice",
         "justification": "Disclosure banner verified in UI."}
    ]))
    out = tmp_path / "reviewed.json"
    res = runner.invoke(cli.app, ["review", "apply", str(report_path), str(reviews), "--out", str(out)])
    assert res.exit_code == 0, res.output
    before = AuditReport.model_validate_json(report_path.read_text())
    after = AuditReport.model_validate_json(out.read_text())
    v = next(v for v in after.verdicts if v.requirement_id == "TP-TR-01")
    assert v.status.value == "compliant" and v.method == "human"
    assert "Disclosure banner verified" in v.rationale
    assert after.overall_score > before.overall_score

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"requirement_id": "NOPE", "status": "compliant", "reviewer": "x"}]))
    res = runner.invoke(cli.app, ["review", "apply", str(report_path), str(bad)])
    assert res.exit_code == 2
