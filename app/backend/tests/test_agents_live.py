"""Live tests against the real Claude Code CLI (haiku). Skipped unless --run-live / CCAUDITOR_LIVE=1."""

import pytest

from ccauditor import pipeline
from ccauditor.agents import ComplianceJudge, Verifier
from ccauditor.llm.backend import ClaudeCodeBackend
from ccauditor.models import Category, Evidence, EvidenceKind, Requirement, RiskLevel, Status

pytestmark = pytest.mark.live

REQ = Requirement(
    id="AIA-REC-01", policy_id="eu-ai-act", clause_ids=["eu-ai-act/Art.12(1)"], category=Category.RECORD_KEEPING,
    title="Automatic logging of AI decisions",
    statement="The system automatically records events (inputs, outputs, timestamps) for each model decision.",
    llm_guidance="Look for logging of model inputs/outputs with timestamps around predict/decision calls.",
)


def test_live_judge_no_evidence_is_not_compliant():
    b = ClaudeCodeBackend(model="haiku", use_cache=False)
    ev = [Evidence(id="x1", kind=EvidenceKind.DOC, path="README.md", start_line=1, end_line=2,
                   snippet="# Photo sorter\nSorts photos by colour.")]
    v = Verifier().check(ComplianceJudge(b).run(REQ, ev), {"x1"})
    assert v.status in (Status.NON_COMPLIANT, Status.NEEDS_REVIEW)
    assert b.usage.calls == 1


def test_live_pipeline_hybrid_tiny_repo(tmp_path):
    (tmp_path / "README.md").write_text("# HireRank\nRanks job applicants for recruitment. "
                                        "A recruiter reviews every ranking before any decision.\n")
    (tmp_path / "predict.py").write_text("import logging\nlog = logging.getLogger('audit')\n\n"
                                         "def predict(m, x):\n    y = m.predict(x)\n"
                                         "    log.info('prediction input=%s output=%s', x, y)\n    return y\n")
    reqs = [REQ.model_copy(update={"applies_to": [RiskLevel.HIGH]}),
            Requirement(id="HUM-01", policy_id="eu-ai-act", clause_ids=["eu-ai-act/Art.14(1)"],
                        category=Category.HUMAN_OVERSIGHT, title="Human oversight",
                        statement="A natural person reviews automated decisions before they take effect.",
                        applies_to=[RiskLevel.HIGH], llm_guidance="Look for a human review/approval step.")]
    b = ClaudeCodeBackend(model="haiku", use_cache=False)
    rep = pipeline.run_audit(str(tmp_path), ["eu-ai-act"], mode="hybrid", backend=b, requirements_override=reqs)
    assert rep.risk.level == RiskLevel.HIGH
    assert all(v.verified for v in rep.verdicts if v.method != "deterministic")
    print(rep.stats)
