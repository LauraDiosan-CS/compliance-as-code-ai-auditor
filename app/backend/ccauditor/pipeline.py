"""Orchestrator: plans an audit run, routes deterministic vs LLM evaluation, aggregates the report.

Modes
  deterministic : rule engine only, heuristic risk classification, no LLM calls.
  llm           : LLM judge for every requirement (retrieved evidence), LLM risk classification.
  hybrid        : rule engine first; LLM judge only where rules are inconclusive/weak; Verifier on every verdict;
                  conflicts between rules and LLM -> NEEDS_REVIEW (human in the loop).
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from .agents.judge import ComplianceJudge
from .agents.policy_analyst import PolicyAnalyst
from .agents.remediator import ARTIFACT_KINDS, ArtifactGenerator
from .agents.risk import RiskClassifier, heuristic_classify
from .agents.scout import EvidenceScout
from .agents.verifier import Verifier
from .llm.backend import LLMBackend, get_backend, usage_delta
from .models import (
    AuditReport,
    Evidence,
    EvidenceIndex,
    Requirement,
    RiskAssessment,
    RiskLevel,
    Status,
    Verdict,
)

MODES = ("deterministic", "llm", "hybrid")
# Deterministic verdicts below this confidence go to the LLM judge. 0.675 = median of the leave-one-app-out
# choices on the benchmark (app/benchmark/threshold_sweep.py); ~60% of applicable items reach the LLM.
HYBRID_CONFIDENCE_THRESHOLD = 0.675
BORDERLINE_CONFIDENCE = 0.6  # LLM-involved verdicts below this -> NEEDS_REVIEW
ARBITRATION_MARGIN = 0.15  # rules vs LLM hard disagreement: the side this much more confident wins, else NR

Progress = Callable[[str], None] | None


# ------------------------------------------------------------------ integration points (agent A modules)
# Imported lazily so this module can be imported (and unit-tested) independently.


def _get_requirements(policy_id: str) -> list[Requirement]:
    from .policies.loader import get_requirements

    return get_requirements(policy_id)


def _get_policy(policy_id: str):
    from .policies.loader import get_policy

    return get_policy(policy_id)


def _collect(repo_root: str) -> EvidenceIndex:
    from .evidence.collector import collect

    return collect(repo_root)


def _make_retriever(index: EvidenceIndex):
    from .evidence.retriever import Retriever

    return Retriever(index)


def _evaluate_requirement(req: Requirement, repo_root: str, index: EvidenceIndex) -> Verdict:
    from .rules.engine import evaluate_requirement

    return evaluate_requirement(req, repo_root, index)


def _build_scorecard(reqs: list[Requirement], verdicts: list[Verdict]):
    from .report.scoring import build_scorecard

    return build_scorecard(reqs, verdicts)


# ------------------------------------------------------------------ routing / combination (pure functions)


def applies(req: Requirement, risk: RiskAssessment | None) -> bool:
    """Whether a requirement applies at the classified risk tier (unknown tier -> applies)."""
    if risk is None or risk.level == RiskLevel.UNKNOWN or not req.applies_to:
        return True
    if risk.level in req.applies_to:
        return True
    # a prohibited system is at least subject to everything that binds high-risk systems
    return risk.level == RiskLevel.PROHIBITED and RiskLevel.HIGH in req.applies_to


def not_applicable_verdict(req: Requirement, risk: RiskAssessment) -> Verdict:
    return Verdict(
        requirement_id=req.id, status=Status.NOT_APPLICABLE, confidence=max(0.5, risk.confidence),
        rationale=(f"Applies to {', '.join(r.value for r in req.applies_to)} risk systems; this system is "
                   f"classified as {risk.level.value}."),
        method="deterministic", verified=True,
    )


def needs_llm(req: Requirement, det: Verdict | None, threshold: float | None = None) -> bool:
    """Hybrid routing: send to the LLM judge when rules are inconclusive, weak or absent.

    The rule engine grades its confidence (single match, documentation-only claim, regex miss and
    "absent" checks are weak), so the threshold decides how much is double-checked by the LLM.
    """
    threshold = HYBRID_CONFIDENCE_THRESHOLD if threshold is None else threshold
    if det is None:
        return True
    if det.status in (Status.NEEDS_REVIEW, Status.PARTIAL):
        return True
    if det.confidence < threshold:
        return True
    if req.llm_guidance and not req.checks:
        return True
    return False


def _disagree(a: Status, b: Status) -> bool:
    return {a, b} == {Status.COMPLIANT, Status.NON_COMPLIANT}


def combine(det: Verdict | None, llm: Verdict) -> Verdict:
    """Merge deterministic and LLM verdicts. Hard disagreement -> NEEDS_REVIEW with both opinions."""
    if det is None:
        return llm.model_copy(update={"method": "llm"})
    ids = list(dict.fromkeys([*llm.evidence_ids, *det.evidence_ids]))
    gaps = list(dict.fromkeys([*llm.gaps, *det.gaps]))
    if _disagree(det.status, llm.status):
        winner = None
        if llm.confidence - det.confidence >= ARBITRATION_MARGIN:
            winner, loser, wname, lname = llm, det, "LLM judge", "rule engine"
        elif det.confidence - llm.confidence >= ARBITRATION_MARGIN:
            winner, loser, wname, lname = det, llm, "rule engine", "LLM judge"
        if winner is not None:
            return Verdict(
                requirement_id=llm.requirement_id, status=winner.status,
                confidence=round(max(0.0, winner.confidence - 0.1), 3),
                rationale=(f"Rule engine and LLM judge disagree; the {wname} is markedly more confident "
                           f"({winner.confidence:.2f} vs {loser.confidence:.2f}) and is followed.\n"
                           f"LLM judge ({llm.status.value}): {llm.rationale}\n"
                           f"Rule engine ({det.status.value}): {det.rationale}"),
                evidence_ids=list(dict.fromkeys([*winner.evidence_ids, *loser.evidence_ids])),
                gaps=gaps, remediation=llm.remediation or det.remediation,
                method="hybrid", verified=llm.verified,
            )
        return Verdict(
            requirement_id=llm.requirement_id, status=Status.NEEDS_REVIEW,
            confidence=round(min(0.5, det.confidence, llm.confidence), 3),
            rationale=(f"Rule engine and LLM judge disagree - human review required.\n"
                       f"Rule engine ({det.status.value}, conf {det.confidence:.2f}): {det.rationale}\n"
                       f"LLM judge ({llm.status.value}, conf {llm.confidence:.2f}): {llm.rationale}"),
            evidence_ids=ids, gaps=gaps, remediation=llm.remediation or det.remediation,
            method="hybrid", verified=llm.verified,
        )
    if llm.status == det.status:
        conf = min(1.0, max(det.confidence, llm.confidence) + 0.05)
    else:
        conf = llm.confidence
    return Verdict(
        requirement_id=llm.requirement_id, status=llm.status, confidence=round(conf, 3),
        rationale=f"{llm.rationale}\nRule engine ({det.status.value}): {det.rationale}",
        evidence_ids=ids, gaps=gaps, remediation=llm.remediation or det.remediation,
        method="hybrid", verified=llm.verified,
    )


def apply_borderline(v: Verdict) -> Verdict:
    """Human-in-the-loop gate for low-confidence LLM-involved verdicts."""
    if v.method in ("llm", "hybrid") and v.status not in (Status.NEEDS_REVIEW, Status.NOT_APPLICABLE) \
            and v.confidence < BORDERLINE_CONFIDENCE:
        return v.model_copy(update={
            "status": Status.NEEDS_REVIEW,
            "rationale": f"{v.rationale}\nLow confidence ({v.confidence:.2f}) for '{v.status.value}': "
                         "routed to human review.",
        })
    return v


# ------------------------------------------------------------------ main entry point


class _NoVerifier:
    """Pass-through stand-in used for the 'no Verifier' ablation."""

    def check(self, verdict: Verdict, *_a, **_k) -> Verdict:
        return verdict

    def run(self, _req: Requirement, verdict: Verdict, *_a, **_k) -> Verdict:
        return verdict


def _say(progress: Progress, msg: str) -> None:
    if progress:
        try:
            progress(msg)
        except Exception:  # noqa: BLE001
            pass


def load_requirements(policy_ids: list[str], mode: str, backend: LLMBackend | None, model: str | None,
                      progress: Progress = None) -> tuple[list[Requirement], dict[str, str], list[str]]:
    """Curated requirements, or PolicyAnalyst-derived ones when none exist. Returns (reqs, clause_texts, notes)."""
    reqs: list[Requirement] = []
    clause_texts: dict[str, str] = {}
    notes: list[str] = []
    for pid in policy_ids:
        policy = None
        try:
            policy = _get_policy(pid)
            clause_texts.update({c.id: c.text for c in policy.clauses})
        except Exception:  # noqa: BLE001
            pass
        curated: list[Requirement] = []
        try:
            curated = _get_requirements(pid)
        except Exception:  # noqa: BLE001
            curated = []
        if curated:
            reqs.extend(curated)
            continue
        if policy is None:
            raise KeyError(f"Unknown policy: {pid}")
        if mode == "deterministic" or backend is None or policy is None:
            notes.append(f"No curated requirements for policy '{pid}'"
                         + " (PolicyAnalyst needs an LLM mode).")
            continue
        _say(progress, f"PolicyAnalyst: decomposing {len(policy.clauses)} clauses of '{pid}'")
        derived = PolicyAnalyst(backend, model).run(policy)
        notes.append(f"{len(derived)} requirements for '{pid}' derived by PolicyAnalyst (LLM).")
        reqs.extend(derived)
    return reqs, clause_texts, notes


def run_audit(
    repo_root: str,
    policy_ids: list[str],
    mode: str = "hybrid",
    backend: LLMBackend | None = None,
    model: str | None = None,
    requirements_override: list[Requirement] | None = None,
    progress: Progress = None,
    verify_with_llm: bool = False,
    index: EvidenceIndex | None = None,
    use_verifier: bool = True,
    hybrid_threshold: float | None = None,
) -> AuditReport:
    """Run one audit. ``use_verifier=False`` disables the Verifier entirely (ablation only)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    t_start = time.perf_counter()
    timings: dict[str, float] = {}
    repo_root = str(Path(repo_root).resolve())

    if mode != "deterministic" and backend is None:
        backend = get_backend(None, model)
    use_llm = mode != "deterministic"
    model = model or (getattr(backend, "model", None) if use_llm else None)
    usage_before = backend.usage.snapshot() if backend is not None else {}

    # 1. requirements
    t = time.perf_counter()
    notes: list[str] = []
    if requirements_override is not None:
        reqs = list(requirements_override)
        clause_texts: dict[str, str] = {}
        for pid in policy_ids:
            try:
                clause_texts.update({c.id: c.text for c in _get_policy(pid).clauses})
            except Exception:  # noqa: BLE001
                pass
    else:
        reqs, clause_texts, notes = load_requirements(policy_ids, mode, backend if use_llm else None, model, progress)
    timings["requirements_s"] = time.perf_counter() - t
    _say(progress, f"{len(reqs)} requirements loaded")

    # 2. evidence
    t = time.perf_counter()
    if index is None:
        index = _collect(repo_root)
    retriever = _make_retriever(index)
    by_id: dict[str, Evidence] = {e.id: e for e in index.items}
    timings["evidence_s"] = time.perf_counter() - t
    _say(progress, f"Collected {len(index.items)} evidence chunks from {index.files_scanned} files")

    # 3. risk
    t = time.perf_counter()
    if use_llm:
        risk = RiskClassifier(backend, model).run(index, retriever, use_llm=True)
    else:
        risk = heuristic_classify(index)
    timings["risk_s"] = time.perf_counter() - t
    _say(progress, f"Risk tier: {risk.level.value}")

    # 4. deterministic pass + routing
    t = time.perf_counter()
    verdicts: dict[str, Verdict] = {}
    det_verdicts: dict[str, Verdict] = {}
    to_judge: list[Requirement] = []
    verifier = Verifier(backend if use_llm else None, use_llm=verify_with_llm and use_llm, model=model)
    if not use_verifier:
        verifier = _NoVerifier()
    for req in reqs:
        if not applies(req, risk):
            verdicts[req.id] = not_applicable_verdict(req, risk)
            continue
        det = None
        if mode in ("deterministic", "hybrid"):
            try:
                det = _evaluate_requirement(req, repo_root, index)
            except Exception as e:  # noqa: BLE001
                det = Verdict(requirement_id=req.id, status=Status.NEEDS_REVIEW, confidence=0.0,
                              rationale=f"Rule engine error: {e}", method="deterministic")
            det = verifier.check(det, by_id, require_evidence=False)  # rule citations must exist in the index
            det_verdicts[req.id] = det
        if mode == "llm" or (mode == "hybrid" and needs_llm(req, det, hybrid_threshold)):
            to_judge.append(req)
        else:
            verdicts[req.id] = det  # type: ignore[assignment]
    timings["deterministic_s"] = time.perf_counter() - t

    # 5. LLM judge (concurrent)
    t = time.perf_counter()
    if to_judge:
        _say(progress, f"LLM judge: {len(to_judge)} requirement(s)")
        scout = EvidenceScout(retriever, by_id)
        judge = ComplianceJudge(backend, model)  # type: ignore[arg-type]
        req_by_id = {r.id: r for r in reqs}

        def work(req: Requirement) -> Verdict:
            det = det_verdicts.get(req.id)
            ev = scout.run(req, det)
            llm_v = judge.run(req, ev, det, clause_texts, method="llm" if mode == "llm" else "hybrid")
            provided = {e.id: e for e in ev}
            if det is not None:
                provided.update({i: by_id[i] for i in det.evidence_ids if i in by_id})
            llm_v = verifier.run(req_by_id[req.id], llm_v, provided)
            v = combine(det, llm_v) if mode == "hybrid" else llm_v.model_copy(update={"method": "llm"})
            v = verifier.check(v, provided)
            v = apply_borderline(v)
            _say(progress, f"  {req.id}: {v.status.value} ({v.confidence:.2f})")
            return v

        workers = max(1, int(getattr(backend, "concurrency", 1) or 1))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for req, v in zip(to_judge, ex.map(work, to_judge)):
                verdicts[req.id] = v
    timings["llm_judge_s"] = time.perf_counter() - t

    ordered = [verdicts[r.id] for r in reqs if r.id in verdicts]

    # 6. report
    t = time.perf_counter()
    scorecard, overall = _build_scorecard(reqs, ordered)
    cited: list[str] = []
    for v in ordered:
        cited.extend(v.evidence_ids)
    cited.extend(risk.evidence_ids)
    evidence = [by_id[i] for i in dict.fromkeys(cited) if i in by_id]
    timings["report_s"] = time.perf_counter() - t
    timings["total_s"] = time.perf_counter() - t_start

    llm_stats = usage_delta(usage_before, backend.usage.snapshot()) if backend is not None and use_llm else {}
    stats: dict[str, Any] = {
        "mode": mode,
        "model": model if use_llm else None,
        "backend": getattr(backend, "name", None) if use_llm else None,
        "timings": {k: round(v, 3) for k, v in timings.items()},
        "llm_calls": llm_stats.get("calls", 0),
        "llm_cache_hits": llm_stats.get("cache_hits", 0),
        "llm_failures": llm_stats.get("failures", 0),
        "input_tokens": llm_stats.get("input_tokens", 0),
        "output_tokens": llm_stats.get("output_tokens", 0),
        "cost_usd": llm_stats.get("cost_usd", 0.0),
        "llm_latency_s": llm_stats.get("latency_s", 0.0),
        "llm_cached_cost_usd": llm_stats.get("cached_cost_usd", 0.0),
        "llm_cached_latency_s": llm_stats.get("cached_latency_s", 0.0),
        "llm_cached_input_tokens": llm_stats.get("cached_input_tokens", 0),
        "llm_cached_output_tokens": llm_stats.get("cached_output_tokens", 0),
        "use_verifier": use_verifier,
        "hybrid_threshold": (HYBRID_CONFIDENCE_THRESHOLD if hybrid_threshold is None else hybrid_threshold)
        if mode == "hybrid" else None,
        "verify_with_llm": bool(verify_with_llm and use_llm),
        "n_requirements": len(reqs),
        "n_llm_judged": len(to_judge),
        "n_needs_review": sum(v.status == Status.NEEDS_REVIEW for v in ordered),
        "files_scanned": index.files_scanned,
        "n_evidence_items": len(index.items),
    }
    if notes:
        stats["notes"] = notes
    _say(progress, f"Done: score {overall:.1f} in {timings['total_s']:.1f}s")
    return AuditReport(
        id=uuid.uuid4().hex[:12], target=repo_root, policies=list(policy_ids), mode=mode,  # type: ignore[arg-type]
        risk=risk, requirements=reqs, verdicts=ordered, evidence=evidence,
        scorecard=scorecard, overall_score=overall, stats=stats,
    )


# ------------------------------------------------------------------ helpers


def generate_artifacts(report: AuditReport, kinds: list[str] | None = None, backend: LLMBackend | None = None,
                       model: str | None = None) -> dict[str, str]:
    """Draft compliance artefacts (markdown) from a report. Without a backend, returns templates."""
    gen = ArtifactGenerator(backend, model)
    kinds = list(kinds or ARTIFACT_KINDS)
    if backend is None or len(kinds) == 1:
        return {k: gen.draft_artifact(k, report) for k in kinds}
    with ThreadPoolExecutor(max_workers=max(1, int(getattr(backend, "concurrency", 1)))) as ex:
        return dict(zip(kinds, ex.map(lambda k: gen.draft_artifact(k, report), kinds)))


def explain(report: AuditReport, requirement_id: str) -> str:
    """Human-readable markdown explanation of one verdict: requirement, decision, evidence, gaps."""
    req = next((r for r in report.requirements if r.id == requirement_id), None)
    v = next((x for x in report.verdicts if x.requirement_id == requirement_id), None)
    if req is None or v is None:
        raise KeyError(f"requirement {requirement_id!r} not in report")
    ev = {e.id: e for e in report.evidence}
    out = [
        f"## {req.id}: {req.title}",
        f"*Policy* `{req.policy_id}` - clauses {', '.join(req.clause_ids)} - category `{req.category.value}` - "
        f"severity `{req.severity}`",
        "",
        f"> {req.statement}",
        "",
        f"**Status:** `{v.status.value}`  **Confidence:** {v.confidence:.2f}  **Method:** {v.method}  "
        f"**Verified citations:** {'yes' if v.verified else 'no'}",
        "",
        "### Rationale",
        v.rationale,
    ]
    if v.evidence_ids:
        out += ["", "### Evidence"]
        for i in v.evidence_ids:
            e = ev.get(i)
            if e is None:
                out.append(f"- `{i}` (not included in report)")
                continue
            snippet = e.snippet if len(e.snippet) < 800 else e.snippet[:800] + "\n..."
            out += [f"- `{e.path}:{e.start_line}-{e.end_line}` ({e.kind.value})", "", "```", snippet, "```"]
    if v.gaps:
        out += ["", "### Gaps"] + [f"- {g}" for g in v.gaps]
    if v.remediation:
        out += ["", "### Remediation", v.remediation]
    return "\n".join(out)
