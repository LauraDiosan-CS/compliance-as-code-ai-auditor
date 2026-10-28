"""FastAPI service exposing policies, audits, report comparison and policy diffs.

Run locally: `uvicorn ccauditor.api:app --reload`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ccauditor import __version__
from ccauditor.ci import compare_reports
from ccauditor.models import AuditReport, Requirement
from ccauditor.policies.evolution import affected_reports, diff_policies
from ccauditor.policies.loader import get_policy, get_requirements, list_builtin_policies, parse_policy_markdown
from ccauditor.report.render import to_html, to_json, to_markdown, to_sarif
from ccauditor.review import Review, apply_reviews

SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
                  or os.environ.get("CCAUDITOR_SERVERLESS"))
DEFAULT_MODE: Literal["deterministic", "llm", "hybrid"] = "deterministic" if SERVERLESS else "hybrid"
_REPO_URL = re.compile(r"^https://[\w.-]+(:\d+)?/[\w./~%+-]+?(\.git)?/?$")

app = FastAPI(title="Compliance-as-Code AI Auditor", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CCAUDITOR_CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    repo_url: str | None = None
    repo_path: str | None = None
    policies: list[str] = Field(default_factory=lambda: ["eu-ai-act"])
    mode: Literal["deterministic", "llm", "hybrid"] | None = None
    model: str | None = None
    requirements: list[Requirement] | None = None  # optional custom requirements


class CompareRequest(BaseModel):
    baseline: AuditReport
    current: AuditReport
    changed_files: list[str] | None = None


class PolicyDiffRequest(BaseModel):
    old: str  # policy markdown
    new: str
    requirements: list[Requirement] | None = None
    reports: list[AuditReport] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    report: AuditReport
    reviews: list[Review]


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__, "default_mode": DEFAULT_MODE, "serverless": SERVERLESS}


@app.get("/policies")
def policies() -> list[dict[str, Any]]:
    items = list_builtin_policies()
    for p in items:  # don't leak server file paths
        p.pop("file", None)
        p.pop("requirements_files", None)
    return items


@app.get("/policies/{policy_id}")
def policy_detail(policy_id: str) -> dict[str, Any]:
    try:
        policy = get_policy(policy_id)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown policy {policy_id}") from exc
    return {
        "policy": policy.model_dump(mode="json"),
        "requirements": [r.model_dump(mode="json") for r in get_requirements(policy_id)],
    }


def _clone(url: str, dest: Path) -> None:
    if not _REPO_URL.match(url):
        raise HTTPException(400, "repo_url must be a public https git URL")
    if not shutil.which("git"):
        raise HTTPException(500, "git is not available on this server")
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--", url, str(dest)],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if proc.returncode != 0:
        raise HTTPException(400, f"git clone failed: {proc.stderr.strip()[-500:]}")


@app.post("/audit")
def audit(req: AuditRequest) -> AuditReport:
    from ccauditor.cli import resolve_run_audit  # local import keeps API startup light

    if not (req.repo_url or req.repo_path):
        raise HTTPException(400, "Provide repo_url or repo_path")
    mode = req.mode or DEFAULT_MODE
    run_audit = resolve_run_audit()
    tmp: str | None = None
    try:
        if req.repo_url:
            tmp = tempfile.mkdtemp(prefix="ccauditor-")
            root = Path(tmp) / "repo"
            _clone(req.repo_url, root)
            target_name = req.repo_url
        else:
            if SERVERLESS:
                raise HTTPException(400, "repo_path is disabled on serverless deployments; use repo_url")
            root = Path(req.repo_path or "").expanduser().resolve()
            if not root.is_dir():
                raise HTTPException(400, f"Not a directory: {req.repo_path}")
            target_name = str(root)
        try:
            report = run_audit(
                str(root), req.policies, mode=mode, backend=None, model=req.model,
                requirements_override=req.requirements,
            )
        except KeyError as exc:
            raise HTTPException(400, str(exc)) from exc
        report.target = target_name
        return report
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


@app.post("/reports/compare")
def reports_compare(req: CompareRequest) -> dict[str, Any]:
    return compare_reports(req.baseline, req.current, req.changed_files)


_RENDER = {
    "json": (to_json, "application/json"),
    "md": (to_markdown, "text/markdown"),
    "sarif": (to_sarif, "application/sarif+json"),
    "html": (to_html, "text/html"),
}


@app.post("/reports/render")
def reports_render(report: AuditReport, format: str = "md") -> Response:
    if format not in _RENDER:
        raise HTTPException(400, f"format must be one of {', '.join(_RENDER)}")
    fn, media = _RENDER[format]
    return Response(content=fn(report), media_type=media)


@app.post("/reports/review")
def reports_review(req: ReviewRequest) -> AuditReport:
    try:
        return apply_reviews(req.report, req.reviews)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/policies/diff")
def policies_diff(req: PolicyDiffRequest) -> dict[str, Any]:
    old, new = parse_policy_markdown(req.old), parse_policy_markdown(req.new)
    reqs = req.requirements if req.requirements is not None else get_requirements(new.id)
    diff = diff_policies(old, new, reqs)
    if req.reports:
        diff["affected_reports"] = affected_reports(diff, req.reports)
    return diff
