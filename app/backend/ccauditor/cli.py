"""Command line interface: `ccauditor audit|policies|diff-policy|ci|review`."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import typer

from ccauditor.ci import changed_files, compare_reports, open_gaps, severities_at_or_above, should_fail
from ccauditor.evidence.collector import collect
from ccauditor.models import AuditReport, Requirement
from ccauditor.policies.evolution import affected_reports, diff_policies
from ccauditor.policies.loader import get_requirements, list_builtin_policies, load_policy, load_requirements
from ccauditor.report.render import to_html, to_json, to_markdown, to_sarif
from ccauditor.report.scoring import build_scorecard
from ccauditor.review import apply_reviews
from ccauditor.rules.engine import evaluate_all

app = typer.Typer(help="Compliance-as-Code AI Auditor", no_args_is_help=True, add_completion=False)
review_app = typer.Typer(help="Human-in-the-loop review of audit reports", no_args_is_help=True)
app.add_typer(review_app, name="review")

RENDERERS: dict[str, Callable[[AuditReport], str]] = {
    "json": to_json,
    "md": to_markdown,
    "markdown": to_markdown,
    "sarif": to_sarif,
    "html": to_html,
}


# ------------------------------------------------------------------ audit plumbing


def _deterministic_audit(
    repo_root: str,
    policy_ids: list[str],
    mode: str = "deterministic",
    backend: Any = None,
    model: str | None = None,
    requirements_override: list[Requirement] | None = None,
    progress: Callable[[str], None] | None = None,
) -> AuditReport:
    """Fallback used only when ccauditor.pipeline is unavailable: rules-only audit."""
    t0 = time.perf_counter()
    say = progress or (lambda _msg: None)
    if requirements_override is not None:
        requirements = list(requirements_override)
    else:
        requirements = [r for pid in policy_ids for r in get_requirements(pid)]
    say(f"Collecting evidence from {repo_root}")
    index = collect(repo_root)
    say(f"Evaluating {len(requirements)} requirements over {len(index.items)} evidence chunks")
    verdicts = evaluate_all(requirements, repo_root, index)
    cited = {i for v in verdicts for i in v.evidence_ids}
    scorecard, overall = build_scorecard(requirements, verdicts)
    return AuditReport(
        id=uuid.uuid4().hex[:12],
        target=str(repo_root),
        policies=policy_ids,
        mode="deterministic",
        requirements=requirements,
        verdicts=verdicts,
        evidence=[e for e in index.items if e.id in cited],
        scorecard=scorecard,
        overall_score=overall,
        stats={
            "files_scanned": index.files_scanned,
            "evidence_chunks": len(index.items),
            "duration_s": round(time.perf_counter() - t0, 3),
            "llm_calls": 0,
        },
    )


def resolve_run_audit() -> Callable[..., AuditReport]:
    try:
        from ccauditor.pipeline import run_audit  # implemented by the agents/pipeline package
    except ImportError:
        return _deterministic_audit
    return run_audit


def _progress(msg: str) -> None:
    typer.echo(f"[ccauditor] {msg}", err=True)


def _emit(text: str, out: Optional[Path]) -> None:
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}", err=True)
    else:
        typer.echo(text)


def _load_report(path: Path) -> AuditReport:
    return AuditReport.model_validate_json(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ commands


@app.command("policies")
def policies_cmd(as_json: bool = typer.Option(False, "--json", help="Print JSON")) -> None:
    """List built-in policies and their curated requirement counts."""
    items = list_builtin_policies()
    if as_json:
        typer.echo(json.dumps(items, indent=2))
        return
    if not items:
        typer.echo("No built-in policies found.")
        return
    for p in items:
        typer.echo(f"{p['id']:<20} v{p['version']:<12} {p['clauses']:>4} clauses {p['requirements']:>4} reqs  {p['name']}")


@app.command("audit")
def audit_cmd(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, help="Repository to audit"),
    policy: list[str] = typer.Option(["eu-ai-act"], "--policy", "-p", help="Policy id (repeatable)"),
    mode: str = typer.Option("hybrid", "--mode", "-m", help="deterministic | llm | hybrid"),
    fmt: str = typer.Option("md", "--format", "-f", help="json | md | sarif | html"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output file (default: stdout)"),
    model: Optional[str] = typer.Option(None, "--model", help="LLM model alias, e.g. sonnet"),
    requirements: Optional[Path] = typer.Option(
        None, "--requirements", "-r", exists=True, dir_okay=False, help="Custom requirements YAML"
    ),
) -> None:
    """Audit a repository against one or more policies."""
    if mode not in ("deterministic", "llm", "hybrid"):
        raise typer.BadParameter("mode must be deterministic, llm or hybrid", param_hint="--mode")
    if fmt not in RENDERERS:
        raise typer.BadParameter(f"format must be one of {', '.join(RENDERERS)}", param_hint="--format")
    override = load_requirements(requirements) if requirements else None
    run_audit = resolve_run_audit()
    report = run_audit(
        str(repo.resolve()), list(policy), mode=mode, backend=None, model=model,
        requirements_override=override, progress=_progress,
    )
    _emit(RENDERERS[fmt](report), out)
    _progress(f"Overall score {report.overall_score:.1f}/100 across {len(report.verdicts)} requirements")


@app.command("diff-policy")
def diff_policy_cmd(
    old: Path = typer.Argument(..., exists=True, dir_okay=False),
    new: Path = typer.Argument(..., exists=True, dir_okay=False),
    requirements: Optional[Path] = typer.Option(None, "--requirements", "-r", exists=True, dir_okay=False),
    report: list[Path] = typer.Option([], "--report", help="Previous audit report(s) to check for impact"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show clause changes between two policy versions and the impacted requirements."""
    old_p, new_p = load_policy(old), load_policy(new)
    reqs = load_requirements(requirements) if requirements else get_requirements(new_p.id)
    diff = diff_policies(old_p, new_p, reqs)
    if report:
        diff["affected_reports"] = affected_reports(diff, [_load_report(r) for r in report])
    if as_json:
        typer.echo(json.dumps(diff, indent=2))
        return
    typer.echo(f"Policy {new_p.id}: {diff['old_version']} -> {diff['new_version']}")
    for key in ("added", "removed"):
        typer.echo(f"{key.capitalize()} clauses: {len(diff[key])}")
        for c in diff[key]:
            typer.echo(f"  {c['id']} {c['title']}")
    typer.echo(f"Modified clauses: {len(diff['modified'])}")
    for c in diff["modified"]:
        typer.echo(f"  {c['id']} (similarity {c['similarity']})")
    typer.echo(f"Affected requirements: {len(diff['affected_requirements'])}")
    for a in diff["affected_requirements"]:
        typer.echo(f"  {a['requirement_id']} {a['title']}: {'; '.join(a['reasons'])}")
    for r in diff.get("affected_reports", []):
        typer.echo(f"Report {r['report_id']} needs re-audit for {', '.join(r['requirements'])}")


@app.command("ci")
def ci_cmd(
    repo: Path = typer.Argument(..., exists=True, file_okay=False),
    baseline: Optional[Path] = typer.Option(None, "--baseline", "-b", exists=True, dir_okay=False),
    base_ref: Optional[str] = typer.Option(None, "--base-ref", help="Git ref to diff against, e.g. origin/main"),
    fail_on: str = typer.Option("high", "--fail-on", help="Fail on regressions of this severity or worse"),
    policy: list[str] = typer.Option([], "--policy", "-p"),
    mode: str = typer.Option("deterministic", "--mode", "-m"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Write current report JSON here"),
    sarif: Optional[Path] = typer.Option(None, "--sarif", help="Write SARIF here"),
) -> None:
    """Re-audit in CI and exit 1 on regressions (vs baseline) or open gaps at --fail-on severity."""
    severities = severities_at_or_above(fail_on)
    base = _load_report(baseline) if baseline else None
    policies = list(policy) or (base.policies if base else ["eu-ai-act"])
    changed: list[str] | None = None
    if base_ref:
        try:
            changed = changed_files(repo, base_ref)
            _progress(f"{len(changed)} file(s) changed since {base_ref}")
        except Exception as exc:  # noqa: BLE001 - CI should still run without git history
            _progress(f"Could not compute changed files: {exc}")
    current = resolve_run_audit()(str(repo.resolve()), policies, mode=mode, progress=_progress)
    if out:
        _emit(to_json(current), out)
    if sarif:
        _emit(to_sarif(current), sarif)

    failed = False
    if base:
        diff = compare_reports(base, current, changed)
        typer.echo(f"Score {diff['baseline_score']:.1f} -> {diff['current_score']:.1f} ({diff['score_delta']:+.1f})")
        for r in diff["regressions"]:
            lost = f" (lost evidence: {', '.join(r['lost_evidence'])})" if r["lost_evidence"] else ""
            typer.echo(f"REGRESSION [{r['severity']}] {r['requirement_id']} {r['from']} -> {r['to']}{lost}")
        for r in diff["improvements"]:
            typer.echo(f"improved   [{r['severity']}] {r['requirement_id']} {r['from']} -> {r['to']}")
        failed = should_fail(diff, severities)
    else:
        gaps = open_gaps(current, severities)
        for g in gaps:
            typer.echo(f"GAP [{g['severity']}] {g['requirement_id']} {g['title']}")
        failed = bool(gaps)
    typer.echo("CI result: FAIL" if failed else "CI result: PASS")
    raise typer.Exit(code=1 if failed else 0)


@review_app.command("apply")
def review_apply_cmd(
    report: Path = typer.Argument(..., exists=True, dir_okay=False),
    reviews: Path = typer.Argument(..., exists=True, dir_okay=False),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Default: <report>.reviewed.json"),
) -> None:
    """Apply human review decisions (JSON list of {requirement_id, status, reviewer, justification})."""
    data = json.loads(reviews.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("reviews", [])
    try:
        updated = apply_reviews(_load_report(report), data)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    target = out or report.with_name(report.stem + ".reviewed.json")
    _emit(to_json(updated), target)
    typer.echo(f"Applied {len(data)} review(s); overall score {updated.overall_score:.1f}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
