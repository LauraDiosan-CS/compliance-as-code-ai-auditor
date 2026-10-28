"""CLI additions used by the CI workflow: ci --markdown-summary/--sarif-prefix, artifacts, explain."""

import json

from typer.testing import CliRunner

from ccauditor import cli
from ccauditor.agents import ARTIFACT_KINDS
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


def _use_fixture_requirements(monkeypatch):
    from ccauditor.policies.loader import load_requirements

    reqs = load_requirements(POLICIES / "test-policy.yaml")
    monkeypatch.setattr(
        cli, "resolve_run_audit",
        lambda: lambda root, pids, **kw: cli._deterministic_audit(root, pids, requirements_override=reqs),
    )


def test_ci_markdown_summary_and_sarif_prefix(repo, tmp_path, monkeypatch):
    _use_fixture_requirements(monkeypatch)
    baseline = _audit_json(repo, tmp_path, "baseline.json")
    main = repo / "app" / "main.py"
    main.write_text(main.read_text().replace("logger.info(", "print("))

    summary, sarif = tmp_path / "out" / "summary.md", tmp_path / "out" / "ci.sarif"
    res = runner.invoke(cli.app, [
        "ci", str(repo), "--baseline", str(baseline), "--fail-on", "high",
        "--markdown-summary", str(summary), "--sarif", str(sarif), "--sarif-prefix", "apps/demo/",
    ])
    assert res.exit_code == 1, res.output
    md = summary.read_text()
    assert md.startswith("<!-- ccauditor-ci -->")
    assert "**FAIL**" in md and "### Regressions" in md
    assert "**TP-REC-01**" in md and "`app/main.py`" in md
    run = json.loads(sarif.read_text())["runs"][0]
    arts = [loc["physicalLocation"]["artifactLocation"] for r in run["results"] for loc in r["locations"]]
    assert arts and all(a["uri"].startswith("apps/demo/") and "uriBaseId" not in a for a in arts)
    assert "originalUriBaseIds" not in run

    # no baseline -> open gaps section, PASS when threshold is critical
    res = runner.invoke(cli.app, ["ci", str(repo), "-p", "test-policy", "--fail-on", "critical",
                                  "--markdown-summary", str(summary)])
    assert res.exit_code == 0, res.output
    assert "**PASS**" in summary.read_text() and "No baseline report" in summary.read_text()


def test_artifacts_offline(repo, tmp_path):
    report = _audit_json(repo, tmp_path)
    out = tmp_path / "artifacts"
    res = runner.invoke(cli.app, ["artifacts", str(report), "--kind", "risk_assessment",
                                  "--kind", "model_card", "--out", str(out), "--offline"])
    assert res.exit_code == 0, res.output
    assert sorted(p.name for p in out.iterdir()) == ["model_card.md", "risk_assessment.md"]
    assert all(p.read_text().strip() for p in out.iterdir())

    res = runner.invoke(cli.app, ["artifacts", str(report), "--kind", "nope", "--offline"])
    assert res.exit_code != 0
    assert set(cli.ARTIFACT_KIND_NAMES) == set(ARTIFACT_KINDS)


def test_artifacts_with_fake_backend(repo, tmp_path, monkeypatch):
    from ccauditor.llm import backend as llm_backend

    fake = llm_backend.FakeBackend({"markdown": "# Drafted by fake LLM\n\nBody."})
    monkeypatch.setattr(llm_backend, "get_backend", lambda name=None, model=None, **kw: fake)
    report = _audit_json(repo, tmp_path)
    out = tmp_path / "drafts"
    res = runner.invoke(cli.app, ["artifacts", str(report), "-k", "transparency_notice", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert (out / "transparency_notice.md").read_text().startswith("# Drafted by fake LLM")
    assert len(fake.calls) == 1


def test_explain(repo, tmp_path):
    report = _audit_json(repo, tmp_path)
    rid = AuditReport.model_validate_json(report.read_text()).verdicts[0].requirement_id
    res = runner.invoke(cli.app, ["explain", str(report), rid])
    assert res.exit_code == 0, res.output
    assert f"## {rid}:" in res.stdout and "**Status:**" in res.stdout
    res = runner.invoke(cli.app, ["explain", str(report), "NOPE-01"])
    assert res.exit_code == 2
