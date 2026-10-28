"""Pipeline tests: routing, combination, HITL gate, and an end-to-end run on a tiny temp repo (FakeBackend only)."""

import re

import pytest

from ccauditor import pipeline
from ccauditor.llm.backend import FakeBackend
from ccauditor.models import (
    Category,
    Requirement,
    RiskAssessment,
    RiskLevel,
    RuleCheck,
    Status,
    Verdict,
)


def V(status, conf=0.9, ids=(), method="deterministic", rid="R"):
    return Verdict(requirement_id=rid, status=status, confidence=conf, rationale=f"{status.value} because",
                   evidence_ids=list(ids), method=method)


def R(rid="R", checks=(), guidance="", applies=(RiskLevel.HIGH, RiskLevel.LIMITED, RiskLevel.MINIMAL)):
    return Requirement(id=rid, policy_id="p", clause_ids=["p/1"], category=Category.RECORD_KEEPING, title=rid,
                       statement="s", checks=list(checks), llm_guidance=guidance, applies_to=list(applies))


CHECK = RuleCheck(type="pattern", pattern="x")

# ------------------------------------------------------------------ routing


@pytest.mark.parametrize(
    "req,det,expected",
    [
        (R(checks=[CHECK]), V(Status.COMPLIANT, 0.9), False),
        (R(checks=[CHECK]), V(Status.NON_COMPLIANT, 0.8), False),
        (R(checks=[CHECK]), V(Status.NEEDS_REVIEW, 0.2), True),
        (R(checks=[CHECK]), V(Status.PARTIAL, 0.9), True),
        (R(checks=[CHECK]), V(Status.COMPLIANT, 0.7), True),  # weak rule confidence
        (R(guidance="look for X"), V(Status.COMPLIANT, 0.9), True),  # guidance, no checks
        (R(checks=[CHECK], guidance="look for X"), V(Status.COMPLIANT, 0.9), False),
        (R(), None, True),
    ],
)
def test_hybrid_routing(req, det, expected):
    assert pipeline.needs_llm(req, det) is expected


def test_disagreement_goes_to_review_with_both_opinions():
    det = V(Status.COMPLIANT, 0.9, ids=["a"])
    llm = V(Status.NON_COMPLIANT, 0.85, ids=["b"], method="hybrid")
    out = pipeline.combine(det, llm)
    assert out.status == Status.NEEDS_REVIEW and out.method == "hybrid"
    assert "Rule engine (compliant" in out.rationale and "LLM judge (non_compliant" in out.rationale
    assert out.evidence_ids == ["b", "a"] and out.confidence <= 0.5


def test_agreement_boosts_confidence_and_llm_wins_soft_disagreement():
    out = pipeline.combine(V(Status.COMPLIANT, 0.7, ids=["a"]), V(Status.COMPLIANT, 0.8, ids=["a"], method="hybrid"))
    assert out.status == Status.COMPLIANT and out.confidence == pytest.approx(0.85)
    out = pipeline.combine(V(Status.PARTIAL, 0.5), V(Status.NON_COMPLIANT, 0.8, method="hybrid"))
    assert out.status == Status.NON_COMPLIANT and out.confidence == 0.8
    assert pipeline.combine(None, V(Status.PARTIAL, method="hybrid")).method == "llm"


def test_borderline_gate():
    assert pipeline.apply_borderline(V(Status.COMPLIANT, 0.55, method="llm")).status == Status.NEEDS_REVIEW
    assert pipeline.apply_borderline(V(Status.COMPLIANT, 0.65, method="llm")).status == Status.COMPLIANT
    # rule-engine verdicts keep their own semantics
    assert pipeline.apply_borderline(V(Status.PARTIAL, 0.5)).status == Status.PARTIAL


def test_applies():
    high_only = R(applies=[RiskLevel.HIGH])
    ra = lambda lv: RiskAssessment(level=lv, rationale="")  # noqa: E731
    assert pipeline.applies(high_only, ra(RiskLevel.HIGH))
    assert not pipeline.applies(high_only, ra(RiskLevel.MINIMAL))
    assert pipeline.applies(high_only, ra(RiskLevel.PROHIBITED))
    assert pipeline.applies(high_only, ra(RiskLevel.UNKNOWN))
    assert pipeline.applies(high_only, None)


# ------------------------------------------------------------------ end-to-end on a tiny repo


@pytest.fixture()
def tiny_repo(tmp_path):
    (tmp_path / "README.md").write_text(
        "# HireRank\n\nHireRank ranks job applicants for recruitment using a gradient boosting model.\n"
        "A recruiter reviews every ranking before a decision is made.\n")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "predict.py").write_text(
        "import logging\n\nlogger = logging.getLogger('audit')\n\n\n"
        "def predict(model, features):\n"
        "    score = model.predict(features)\n"
        "    logger.info('prediction input=%s output=%s', features, score)\n"
        "    return score\n")
    (tmp_path / "app" / "config.yaml").write_text("retention:\n  days: 30\n")
    return tmp_path


def _requirements():
    return [
        # rules pass clearly -> no LLM in hybrid
        Requirement(id="REC-01", policy_id="t", clause_ids=["t/1"], category=Category.RECORD_KEEPING,
                    title="Prediction logging", statement="Model predictions are logged.",
                    applies_to=[RiskLevel.HIGH],
                    checks=[RuleCheck(type="pattern", kinds=["code"], pattern=r"logger\.info\(.*prediction")],
                    evidence_queries=["logger prediction"]),
        # no checks + guidance -> LLM judge
        Requirement(id="HUM-01", policy_id="t", clause_ids=["t/2"], category=Category.HUMAN_OVERSIGHT,
                    title="Human review", statement="A human reviews each automated decision.",
                    applies_to=[RiskLevel.HIGH], llm_guidance="Look for a human-in-the-loop review step.",
                    evidence_queries=["recruiter reviews ranking"]),
        # rules say compliant (file exists); LLM says non_compliant -> disagreement when routed
        Requirement(id="DOC-01", policy_id="t", clause_ids=["t/3"], category=Category.TECHNICAL_DOCUMENTATION,
                    title="Docs", statement="Technical documentation describes the model's limitations.",
                    applies_to=[RiskLevel.HIGH], llm_guidance="limitations section",
                    checks=[RuleCheck(type="file_exists", globs=["README.md"])]),
        # only for limited-risk systems -> not applicable
        Requirement(id="TRA-01", policy_id="t", clause_ids=["t/4"], category=Category.TRANSPARENCY,
                    title="Chatbot disclosure", statement="Users are told they talk to an AI.",
                    applies_to=[RiskLevel.LIMITED]),
    ]


def make_responder():
    def responder(system, prompt):
        if system.startswith("You are RiskClassifier"):
            return {"level": "high", "rationale": "Recruitment (Annex III 4(a)).", "triggers": ["Annex III 4(a)"],
                    "evidence_ids": ["E1"], "confidence": 0.9}
        if system.startswith("You are ComplianceJudge"):
            rid = re.search(r"Requirement (\S+) \[", prompt).group(1)
            aliases = re.findall(r"\[(E\d+)\] kind=", prompt)
            if rid == "HUM-01":
                readme = re.search(r"\[(E\d+)\] kind=doc file=README\.md", prompt).group(1)
                return {"status": "compliant", "confidence": 0.8, "rationale": f"{readme}: recruiter reviews.",
                        "evidence_ids": [readme, "E999"], "gaps": [], "remediation": ""}
            if rid == "DOC-01":
                return {"status": "non_compliant", "confidence": 0.85, "rationale": "No limitations section.",
                        "evidence_ids": aliases[:1], "gaps": ["limitations"], "remediation": "Add limitations."}
            return {"status": "compliant", "confidence": 0.95, "rationale": "logged", "evidence_ids": aliases[:1]}
        raise AssertionError(f"unexpected agent: {system[:40]}")

    return responder


def test_run_audit_hybrid_end_to_end(tiny_repo, monkeypatch):
    real = pipeline._evaluate_requirement

    def weak_doc_rule(req, root, index):  # weak rule verdict -> routed to the LLM, which disagrees
        v = real(req, root, index)
        return v.model_copy(update={"confidence": 0.7}) if req.id == "DOC-01" else v

    monkeypatch.setattr(pipeline, "_evaluate_requirement", weak_doc_rule)
    fb = FakeBackend(make_responder())
    msgs = []
    rep = pipeline.run_audit(str(tiny_repo), ["t"], mode="hybrid", backend=fb,
                             requirements_override=_requirements(), progress=msgs.append)
    by = {v.requirement_id: v for v in rep.verdicts}
    assert rep.risk.level == RiskLevel.HIGH and rep.risk.evidence_ids
    assert by["REC-01"].status == Status.COMPLIANT and by["REC-01"].method == "deterministic"
    assert by["HUM-01"].status == Status.COMPLIANT and by["HUM-01"].method == "hybrid"
    assert by["HUM-01"].verified and "E999" not in by["HUM-01"].evidence_ids
    assert by["DOC-01"].status == Status.NEEDS_REVIEW and "disagree" in by["DOC-01"].rationale
    assert by["TRA-01"].status == Status.NOT_APPLICABLE
    # only cited evidence in the report, and every cited id resolves
    ev_ids = {e.id for e in rep.evidence}
    for v in rep.verdicts:
        assert set(v.evidence_ids) <= ev_ids
    assert len(rep.evidence) < rep.stats["n_evidence_items"] or rep.stats["n_evidence_items"] <= 3
    s = rep.stats
    assert s["mode"] == "hybrid" and s["n_requirements"] == 4 and s["n_llm_judged"] == 2
    assert s["llm_calls"] == 3  # risk + 2 judge calls (REC-01 settled by rules, TRA-01 not applicable)
    assert s["files_scanned"] >= 3 and "total_s" in s["timings"]
    assert rep.scorecard and msgs
    md = pipeline.explain(rep, "HUM-01")
    assert "HUM-01" in md and "README.md" in md


def test_run_audit_deterministic_makes_no_llm_calls(tiny_repo):
    fb = FakeBackend(make_responder())
    rep = pipeline.run_audit(str(tiny_repo), ["t"], mode="deterministic", backend=fb,
                             requirements_override=_requirements())
    assert fb.calls == [] and rep.stats["llm_calls"] == 0
    by = {v.requirement_id: v for v in rep.verdicts}
    assert rep.risk.level == RiskLevel.HIGH  # heuristic: "job applicants", "recruitment"
    assert by["REC-01"].status == Status.COMPLIANT
    assert by["HUM-01"].status == Status.NEEDS_REVIEW
    assert all(v.method == "deterministic" for v in rep.verdicts)


def test_run_audit_llm_mode_judges_everything(tiny_repo):
    fb = FakeBackend(make_responder())
    rep = pipeline.run_audit(str(tiny_repo), ["t"], mode="llm", backend=fb, requirements_override=_requirements())
    applicable = [v for v in rep.verdicts if v.status != Status.NOT_APPLICABLE]
    assert len(applicable) == 3 and all(v.method == "llm" for v in applicable)
    assert rep.stats["llm_calls"] == 4
    assert {v.requirement_id: v.status for v in applicable}["DOC-01"] == Status.NON_COMPLIANT


def test_run_audit_policy_analyst_fallback(tiny_repo, monkeypatch):
    from ccauditor.models import Clause, Policy

    pol = Policy(id="acme-ai-policy", name="ACME", kind="internal_policy",
                 clauses=[Clause(id="acme-ai-policy/POL-1", policy_id="acme-ai-policy", title="Logging",
                                 text="All model predictions must be logged.")])
    monkeypatch.setattr(pipeline, "_get_requirements", lambda pid: [])
    monkeypatch.setattr(pipeline, "_get_policy", lambda pid: pol)

    base = make_responder()

    def responder(system, prompt):
        if system.startswith("You are PolicyAnalyst"):
            return {"requirements": [{"clause_ids": ["acme-ai-policy/POL-1"], "category": "record_keeping",
                                      "title": "Prediction logging", "statement": "Predictions are logged.",
                                      "applies_to": ["high", "limited", "minimal"], "severity": "high",
                                      "evidence_queries": ["logger prediction"], "llm_guidance": "logger calls"}]}
        return base(system, prompt.replace("Requirement AAP-REC-01", "Requirement REC-01"))

    rep = pipeline.run_audit(str(tiny_repo), ["acme-ai-policy"], mode="hybrid", backend=FakeBackend(responder))
    assert [r.id for r in rep.requirements] == ["AAP-REC-01"]
    assert rep.verdicts[0].method == "hybrid" and rep.verdicts[0].status == Status.COMPLIANT
    assert "PolicyAnalyst" in " ".join(rep.stats.get("notes", []))


def test_generate_artifacts(tiny_repo):
    rep = pipeline.run_audit(str(tiny_repo), ["t"], mode="deterministic", requirements_override=_requirements())
    arts = pipeline.generate_artifacts(rep, ["model_card", "risk_assessment"], backend=None)
    assert set(arts) == {"model_card", "risk_assessment"} and all(a.startswith("# ") for a in arts.values())
    fb = FakeBackend({"markdown": "# Transparency notice"})
    assert pipeline.generate_artifacts(rep, ["transparency_notice"], fb)["transparency_notice"] == "# Transparency notice"


def test_unknown_policy_raises_keyerror(tiny_repo, monkeypatch):
    def unknown(pid):
        raise KeyError(pid)

    monkeypatch.setattr(pipeline, "_get_requirements", lambda pid: [])
    monkeypatch.setattr(pipeline, "_get_policy", unknown)
    with pytest.raises(KeyError):
        pipeline.run_audit(str(tiny_repo), ["nope"], mode="deterministic")
