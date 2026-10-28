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
    # graded confidence: depends on the strength of the deciding checks, not only on the status
    assert 0.55 <= verdicts["TP-REC-01"].confidence <= 0.95
    assert 0.55 <= verdicts["TP-SEC-01"].confidence <= 0.95
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


# ---------------------------------------------------------------- comment masking / graded confidence


def _mini_repo(tmp_path, files: dict[str, str]):
    from ccauditor.evidence.collector import collect

    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path, collect(tmp_path)


LOG_CHECK = RuleCheck(type="pattern", kinds=["code"], pattern=r"logger\.info\(.*prediction")


def test_commented_out_code_does_not_satisfy_present_check(tmp_path):
    repo, idx = _mini_repo(tmp_path, {
        "app/main.py": 'score = model.predict(x)\n# logger.info(f"prediction {score}")\n# TODO: add audit logging\n',
        "web/app.ts": '// logger.info("prediction", score)\n/* logger.info("prediction") */\nconst a = 1;\n',
    })
    v = evaluate_requirement(_req(LOG_CHECK), repo, idx)
    assert v.status == Status.NON_COMPLIANT
    assert "only commented-out" in v.rationale
    assert v.confidence >= 0.7  # intent without implementation is a fairly strong negative signal


def test_string_literals_are_not_comments(tmp_path):
    repo, idx = _mini_repo(tmp_path, {
        "app/main.py": 'url = "http://x#frag"\nlogger.info("prediction %s # done", score)\n',
        "web/app.ts": 'const u = "a//b"; logger.info("prediction", score);\n',
    })
    v = evaluate_requirement(_req(LOG_CHECK), repo, idx)
    assert v.status == Status.COMPLIANT and len(v.evidence_ids) == 2


def test_docstring_does_not_trip_absent_check(tmp_path):
    repo, idx = _mini_repo(tmp_path, {
        "app/api.py": '"""API. Emotion recognition is deliberately not supported."""\n\ndef f():\n'
                      '    """No emotion recognition here either."""\n    return 1\n',
    })
    absent = _req(RuleCheck(type="pattern", kinds=["code"], pattern="emotion recognition", expect="absent"))
    v = evaluate_requirement(absent, repo, idx)
    assert v.status == Status.COMPLIANT
    assert v.confidence <= 0.7  # absence of a pattern is weak evidence
    (repo / "app" / "emo.py").write_text("def run_emotion recognition(): pass\nx = 'emotion recognition'\n")
    from ccauditor.evidence.collector import collect

    v2 = evaluate_requirement(absent, repo, collect(repo))
    assert v2.status == Status.NON_COMPLIANT


def test_disabled_feature_flag_is_not_evidence(tmp_path):
    repo, idx = _mini_repo(tmp_path, {"app/main.py": "override_allowed = False\n"})
    req = _req(RuleCheck(type="pattern", kinds=["code"], pattern="override"))
    assert evaluate_requirement(req, repo, idx).status == Status.NON_COMPLIANT
    repo2, idx2 = _mini_repo(tmp_path / "b", {"app/main.py": "def override(decision_id):\n    return 1\n"})
    assert evaluate_requirement(req, repo2, idx2).status == Status.COMPLIANT


def test_documentation_claim_is_weaker_than_code(tmp_path):
    check = RuleCheck(type="pattern", pattern=r"human review")
    repo, idx = _mini_repo(tmp_path, {"README.md": "Fully compliant: every decision gets human review.\n"})
    doc_only = evaluate_requirement(_req(check), repo, idx)
    repo2, idx2 = _mini_repo(tmp_path / "b", {
        "app/a.py": "def human review(): pass\n", "app/b.py": "x = 'human review'\ny = 'human review queue'\n"})
    code = evaluate_requirement(_req(check), repo2, idx2)
    assert doc_only.status == code.status == Status.COMPLIANT
    assert doc_only.confidence < 0.6 < code.confidence
    assert "documentation only" in doc_only.rationale


def test_todo_lines_in_docs_are_ignored(tmp_path):
    repo, idx = _mini_repo(tmp_path, {"docs/ifu.md": "# Instructions\nTODO: describe log retention\n"})
    req = _req(RuleCheck(type="pattern", kinds=["doc"], pattern="log retention"))
    assert evaluate_requirement(req, repo, idx).status == Status.NON_COMPLIANT


def test_mask_non_code_preserves_lines():
    from ccauditor.rules.comments import mask_non_code

    src = 'a = 1  # c\n"""doc\nstring"""\nb = "#x"\n'
    out = mask_non_code("x.py", src)
    assert len(out) == len(src) and out.count("\n") == src.count("\n")
    assert "# c" not in out and "doc" not in out and '"#x"' in out
    html = mask_non_code("r.md", "keep <!-- hidden --> keep\n")
    assert "hidden" not in html and html.count("keep") == 2


def test_explanatory_comment_is_a_weak_claim(tmp_path):
    repo, idx = _mini_repo(tmp_path, {"app/a.py": "try:\n    s = score()\nexcept Exception:\n"
                                                  "    # fail-safe: route to manual review\n    s = None\n"})
    req = _req(RuleCheck(type="pattern", kinds=["code"], pattern="fail[-_ ]?safe"))
    v = evaluate_requirement(req, repo, idx)
    assert v.status == Status.COMPLIANT and v.confidence < 0.6 and v.evidence_ids


def test_comment_kind():
    from ccauditor.rules.comments import comment_kind

    assert comment_kind('    # logger.info(f"prediction {x}")') == "code"
    assert comment_kind("// const a = 1;") == "code"
    assert comment_kind("# TODO: add audit logging") == "todo"
    assert comment_kind("    # Fallback: never guess. The application goes to the queue.") == "prose"
