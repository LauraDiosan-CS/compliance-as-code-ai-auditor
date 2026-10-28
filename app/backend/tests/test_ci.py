import subprocess

from ccauditor.ci import changed_files, compare_reports, open_gaps, severities_at_or_above, should_fail
from ccauditor.models import Status

from helpers import make_report


def test_compare_detects_removed_logging(repo, requirements):
    baseline = make_report(repo, requirements, "base")
    main = repo / "app" / "main.py"
    main.write_text(main.read_text().replace('logger.info("prediction', 'print("prediction'))
    current = make_report(repo, requirements, "cur")
    diff = compare_reports(baseline, current, changed=["app/main.py"])
    reg = {r["requirement_id"]: r for r in diff["regressions"]}
    assert "TP-REC-01" in reg
    assert reg["TP-REC-01"]["from"] == "compliant" and reg["TP-REC-01"]["to"] == "non_compliant"
    assert reg["TP-REC-01"]["lost_evidence"] == ["app/main.py"]
    assert reg["TP-REC-01"]["touches_changed_files"] is True
    assert diff["score_delta"] < 0
    assert should_fail(diff, ("critical", "high"))
    assert not should_fail(diff, ("critical",))

    # reverse direction is an improvement
    back = compare_reports(current, baseline)
    assert [r["requirement_id"] for r in back["improvements"]] == ["TP-REC-01"]
    assert not should_fail(back)


def test_severity_threshold_and_gaps(repo, requirements):
    assert severities_at_or_above("high") == ("critical", "high")
    assert severities_at_or_above("low") == ("critical", "high", "medium", "low")
    report = make_report(repo, requirements)
    gaps = open_gaps(report, ("critical", "high"))
    assert [g["requirement_id"] for g in gaps] == ["TP-SEC-01"]
    assert any(v.status == Status.NON_COMPLIANT for v in report.verdicts)


def test_changed_files(repo):
    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    import shutil

    shutil.rmtree(repo / ".git")
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (repo / "README.md").write_text("changed\n")
    assert changed_files(repo, "HEAD") == ["README.md"]
