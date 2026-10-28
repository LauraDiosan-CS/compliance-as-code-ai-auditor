from ccauditor.models import Category, Requirement, RiskLevel, RuleCheck, Status
from ccauditor.rules.engine import evaluate_all, evaluate_requirement, glob_match


def _req(*checks: RuleCheck, **kw) -> Requirement:
    base = dict(id="R1", policy_id="p", clause_ids=["p/Art.1"], category=Category.OTHER,
                title="t", statement="s")
    base.update(kw)
    return Requirement(checks=list(checks), **base)


def test_glob_match():
    assert glob_match("docs/oversight.md", "docs/*.md")
    assert glob_match("a/b/MODEL_CARD.md", "**/MODEL_CARD*")
    assert glob_match("MODEL_CARD.md", "**/MODEL_CARD*")
    assert glob_match("a/b/c.py", "*.py")
    assert glob_match("src/x/y/z.py", "src/**/z.py")
    assert not glob_match("src/z.js", "*.py")


def test_fixture_requirements(repo, index, requirements):
    verdicts = {v.requirement_id: v for v in evaluate_all(requirements, repo, index)}
    assert verdicts["TP-REC-01"].status == Status.COMPLIANT
    assert verdicts["TP-HO-01"].status == Status.PARTIAL
    assert verdicts["TP-RET-01"].status == Status.COMPLIANT
    assert verdicts["TP-TR-01"].status == Status.NEEDS_REVIEW
    assert verdicts["TP-SEC-01"].status == Status.NON_COMPLIANT
    assert verdicts["TP-REC-01"].confidence == 0.9
    assert verdicts["TP-SEC-01"].confidence == 0.8
    assert verdicts["TP-HO-01"].confidence == 0.5
    assert verdicts["TP-TR-01"].confidence == 0.2
    assert verdicts["TP-SEC-01"].gaps == ["Security policy published"]
    assert verdicts["TP-SEC-01"].remediation
    assert all(v.method == "deterministic" for v in verdicts.values())

    ids = {e.id: e for e in index.items}
    rec = verdicts["TP-REC-01"]
    assert rec.evidence_ids, "pattern match must cite evidence"
    for eid in rec.evidence_ids:
        assert eid in ids
    ev = ids[rec.evidence_ids[0]]
    assert ev.path == "app/main.py" and "logger.info" in ev.snippet
    ret_paths = {ids[i].path for i in verdicts["TP-RET-01"].evidence_ids}
    assert ret_paths == {"config/settings.yaml", "MODEL_CARD.md"}


def test_absent_pattern(repo, index):
    clean = _req(RuleCheck(type="pattern", pattern=r"AKIA[0-9A-Z]{16}", expect="absent"))
    assert evaluate_requirement(clean, repo, index).status == Status.COMPLIANT
    (repo / "app" / "keys.py").write_text('KEY = "AKIAABCDEFGHIJKLMNOP"\n')
    from ccauditor.evidence.collector import collect

    idx2 = collect(repo)
    v = evaluate_requirement(clean, repo, idx2)
    assert v.status == Status.NON_COMPLIANT
    assert any(e.path == "app/keys.py" for e in idx2.items if e.id in v.evidence_ids)


def test_yaml_path_equals_and_kinds(repo, index):
    ok = _req(RuleCheck(type="yaml_path", path="data.encryption", equals=True))
    assert evaluate_requirement(ok, repo, index).status == Status.COMPLIANT
    wrong = _req(RuleCheck(type="yaml_path", path="data.retention.days", equals=365))
    assert evaluate_requirement(wrong, repo, index).status == Status.NON_COMPLIANT
    k8s = _req(RuleCheck(type="yaml_path", kinds=["iac"], path="spec.replicas", equals=2))
    assert evaluate_requirement(k8s, repo, index).status == Status.COMPLIANT


def test_rego_without_opa_is_unknown(repo, index, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    req = _req(RuleCheck(type="rego", rego="package x\nallow := true"))
    v = evaluate_requirement(req, repo, index)
    assert v.status == Status.NEEDS_REVIEW
    mixed = _req(RuleCheck(type="rego", rego="package x\nallow := true"),
                 RuleCheck(type="file_exists", globs=["README*"]))
    assert evaluate_requirement(mixed, repo, index).status == Status.COMPLIANT


def test_not_applicable_by_risk(repo, index, requirements):
    verdicts = {v.requirement_id: v for v in evaluate_all(requirements, repo, index, RiskLevel.MINIMAL)}
    assert verdicts["TP-REC-01"].status == Status.NOT_APPLICABLE  # applies_to: [high]
    assert verdicts["TP-HO-01"].status != Status.NOT_APPLICABLE
    unknown = {v.requirement_id: v for v in evaluate_all(requirements, repo, index, "unknown")}
    assert unknown["TP-REC-01"].status == Status.COMPLIANT
