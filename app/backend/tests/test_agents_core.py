import re

import pytest

from ccauditor.agents import (
    ArtifactGenerator,
    ComplianceJudge,
    EvidenceScout,
    PolicyAnalyst,
    Remediator,
    RiskClassifier,
    Verifier,
    heuristic_classify,
)
from ccauditor.llm.backend import FakeBackend
from ccauditor.models import (
    AuditReport,
    Category,
    Clause,
    Evidence,
    EvidenceIndex,
    EvidenceKind,
    Policy,
    Requirement,
    RiskLevel,
    Status,
    Verdict,
)


def ev(i, path="app/main.py", kind=EvidenceKind.CODE, snippet="logger.info('prediction %s', y)", score=1.0):
    return Evidence(id=f"id{i}", kind=kind, path=path, start_line=1, end_line=5, snippet=snippet, score=score)


REQ = Requirement(id="R-1", policy_id="p", clause_ids=["p/Art.12(1)"], category=Category.RECORD_KEEPING,
                  title="Logging", statement="The system logs every prediction with a timestamp.",
                  evidence_queries=["logging prediction"])


# ------------------------------------------------------------------ Verifier


def test_verifier_drops_hallucinated_ids_and_downgrades():
    v = Verdict(requirement_id="R-1", status=Status.COMPLIANT, confidence=0.9, rationale="ok",
                evidence_ids=["E99", "made-up"], method="llm")
    out = Verifier().check(v, {"id1", "id2"})
    assert out.evidence_ids == []
    assert out.status == Status.NEEDS_REVIEW
    assert out.confidence <= 0.4
    assert out.verified is True
    assert "downgraded" in out.rationale


def test_verifier_keeps_valid_ids_and_partial_drop():
    v = Verdict(requirement_id="R-1", status=Status.PARTIAL, confidence=0.8, rationale="ok",
                evidence_ids=["id1", "bogus"], method="llm")
    out = Verifier().check(v, {"id1"})
    assert out.status == Status.PARTIAL and out.evidence_ids == ["id1"]
    assert out.confidence < 0.8 and out.verified


def test_verifier_non_compliant_without_evidence_is_fine():
    v = Verdict(requirement_id="R-1", status=Status.NON_COMPLIANT, confidence=0.8, rationale="missing")
    out = Verifier().check(v, set())
    assert out.status == Status.NON_COMPLIANT and out.confidence == 0.8


def test_verifier_rule_verdict_without_evidence_not_downgraded():
    v = Verdict(requirement_id="R-1", status=Status.COMPLIANT, confidence=0.9, rationale="absent check passed")
    assert Verifier().check(v, set(), require_evidence=False).status == Status.COMPLIANT


def test_verifier_llm_pass_downgrades_unsupported():
    fb = FakeBackend({"supported": False, "unsupported_ids": ["E1"], "comment": "snippet is unrelated"})
    v = Verdict(requirement_id="R-1", status=Status.COMPLIANT, confidence=0.9, rationale="ok", evidence_ids=["id1"])
    out = Verifier(fb, use_llm=True).run(REQ, v, {"id1": ev(1)})
    assert out.status == Status.NEEDS_REVIEW and "does not support" in out.rationale


# ------------------------------------------------------------------ Judge


def test_judge_maps_aliases_and_builds_prompt():
    captured = {}

    def responder(system, prompt):
        captured["system"], captured["prompt"] = system, prompt
        return {"status": "compliant", "confidence": 0.85, "rationale": "E2 logs predictions",
                "evidence_ids": ["E2", "E7"], "gaps": [], "remediation": ""}

    evidence = [ev(1, snippet="def train(): pass"), ev(2)]
    det = Verdict(requirement_id="R-1", status=Status.PARTIAL, confidence=0.5, rationale="1/2 checks",
                  evidence_ids=["id2"])
    out = ComplianceJudge(FakeBackend(responder)).run(REQ, evidence, det, {"p/Art.12(1)": "Logs shall be kept."})
    assert out.status == Status.COMPLIANT
    assert out.evidence_ids == ["id2", "E7"]  # unknown alias kept verbatim for the Verifier to drop
    assert "[E1]" in captured["prompt"] and "[E2]" in captured["prompt"]
    assert "Logs shall be kept." in captured["prompt"] and "cited=E2" in captured["prompt"]
    assert "Never assume compliance" in captured["system"]
    verified = Verifier().check(out, {e.id: e for e in evidence})
    assert verified.evidence_ids == ["id2"] and verified.status == Status.COMPLIANT


def test_judge_coerces_bad_output_and_survives_failure():
    out = ComplianceJudge(FakeBackend({"status": "Not Applicable", "confidence": 85, "rationale": "",
                                       "evidence_ids": "E1"})).run(REQ, [ev(1)])
    assert out.status == Status.NEEDS_REVIEW and out.confidence == 0.85 and out.evidence_ids == ["id1"]

    def boom(system, prompt):
        raise RuntimeError("cli down")

    out = ComplianceJudge(FakeBackend(boom)).run(REQ, [ev(1)])
    assert out.status == Status.NEEDS_REVIEW and out.confidence == 0.0


# ------------------------------------------------------------------ Scout


class StubRetriever:
    def __init__(self, items):
        self.items = items
        self.queries = []

    def search(self, query, k=8, kinds=None):
        self.queries.append(query)
        words = set(re.findall(r"\w+", query.lower()))
        hits = [e.model_copy(update={"score": float(len(words & set(re.findall(r"\w+", e.snippet.lower()))))})
                for e in self.items]
        return sorted([h for h in hits if h.score > 0], key=lambda e: -e.score)[:k]


def test_scout_merges_dedupes_and_caps():
    items = [ev(i, path=f"f{i}.py", snippet=("logging prediction timestamp " * (i + 1))) for i in range(30)]
    items.append(ev(99, path="pinned.py", snippet="unrelated text"))
    r = StubRetriever(items)
    det = Verdict(requirement_id="R-1", status=Status.PARTIAL, confidence=0.5, rationale="", evidence_ids=["id99"])
    out = EvidenceScout(r, {e.id: e for e in items}, max_chars=2_000).run(REQ, det)
    ids = [e.id for e in out]
    assert ids[0] == "id99"  # deterministic citation pinned first
    assert len(ids) == len(set(ids))
    assert sum(len(e.snippet) for e in out) <= 2_000 + 1_500
    assert any("logging prediction" == q for q in r.queries)  # evidence_queries used
    assert len(r.queries) >= 2  # + keyword expansion


# ------------------------------------------------------------------ Risk


def idx(*items):
    return EvidenceIndex(repo_root="/x", files_scanned=len(items), items=list(items))


@pytest.mark.parametrize(
    "text,level",
    [
        ("HireBot ranks job applicants and does CV screening for recruitment.", RiskLevel.HIGH),
        ("We compute a credit score to decide loan approval.", RiskLevel.HIGH),
        ("A social scoring system rating citizens' trustworthiness.", RiskLevel.PROHIBITED),
        ("A friendly customer support chatbot built on a large language model.", RiskLevel.LIMITED),
        ("A tool that sorts holiday photos by colour.", RiskLevel.MINIMAL),
    ],
)
def test_heuristic_risk(text, level):
    r = heuristic_classify(idx(ev(1, path="README.md", kind=EvidenceKind.DOC, snippet=text)))
    assert r.level == level
    if level != RiskLevel.MINIMAL:
        assert r.triggers and r.evidence_ids == ["id1"]


def test_heuristic_risk_no_docs_is_unknown():
    assert heuristic_classify(idx(ev(1, snippet="x = 1"))).level == RiskLevel.UNKNOWN


def test_llm_risk_classifier_uses_hint_and_filters_ids():
    seen = {}

    def responder(system, prompt):
        seen["prompt"] = prompt
        return {"level": "high", "rationale": "recruitment", "triggers": ["Annex III 4(a)"],
                "evidence_ids": ["E1", "E42"], "confidence": 0.9}

    index = idx(ev(1, path="README.md", kind=EvidenceKind.DOC, snippet="Ranks job applicants for hiring."))
    r = RiskClassifier(FakeBackend(responder)).run(index, None)
    assert r.level == RiskLevel.HIGH and r.evidence_ids == ["id1"] and r.confidence == 0.9
    assert "pre-classifier hint" in seen["prompt"]


# ------------------------------------------------------------------ PolicyAnalyst


def test_policy_analyst_batches_and_parses():
    clauses = [Clause(id="p/Art.12", policy_id="p", title="Record-keeping", text="Heading")]
    clauses += [Clause(id=f"p/Art.12({i})", policy_id="p", text=f"Obligation {i} about logs.", parent_id="p/Art.12")
                for i in range(1, 8)]
    policy = Policy(id="internal-ai-policy", name="Internal", clauses=clauses, kind="internal_policy")

    def responder(system, prompt):
        ids = re.findall(r"\[(p/Art\.12\(\d\))\]", prompt)
        return {"requirements": [{"clause_ids": [ids[0], "bogus/id"], "category": "Record Keeping",
                                  "title": "Logs", "statement": f"The system keeps logs ({ids[0]}).",
                                  "applies_to": ["high", "weird"], "severity": "HIGH",
                                  "evidence_queries": ["logging"], "llm_guidance": "look for loggers"},
                                 {"statement": ""}]}

    fb = FakeBackend(responder)
    pa = PolicyAnalyst(fb, batch_size=3)
    assert [len(b) for b in pa.batches(policy)] == [3, 3, 1]  # parent heading clause excluded
    reqs = pa.run(policy)
    assert len(fb.calls) == 3 and len(reqs) == 3
    assert reqs[0].id == "IAP-REC-01" and reqs[2].id == "IAP-REC-03"
    assert reqs[0].category == Category.RECORD_KEEPING and reqs[0].severity == "high"
    assert reqs[0].clause_ids == ["p/Art.12(1)"] and reqs[0].applies_to == [RiskLevel.HIGH]
    assert reqs[0].checks == []


# ------------------------------------------------------------------ Remediator / artifacts


def _report():
    v = Verdict(requirement_id="R-1", status=Status.NON_COMPLIANT, confidence=0.8, rationale="no logs",
                gaps=["no prediction logging"])
    return AuditReport(id="r1", target="/repo", policies=["p"], mode="hybrid", requirements=[REQ], verdicts=[v],
                       evidence=[])


def test_artifact_generator_template_and_llm():
    rep = _report()
    md = ArtifactGenerator(None).draft_artifact("model_card", rep)
    assert md.startswith("# Model Card") and "no prediction logging" in md
    fb = FakeBackend({"markdown": "# Risk assessment\n..."})
    assert ArtifactGenerator(fb).draft_artifact("risk_assessment", rep).startswith("# Risk assessment")
    assert "no prediction logging" in fb.calls[0][1]
    with pytest.raises(ValueError):
        ArtifactGenerator(None).draft_artifact("poem", rep)


def test_remediator():
    v = _report().verdicts[0]
    assert "no prediction logging" in Remediator(None).run(REQ, v)
    out = Remediator(FakeBackend({"remediation": "Add audit logger", "steps": ["create log.py"]})).run(REQ, v)
    assert out.startswith("Add audit logger") and "1. create log.py" in out
