"""FastAPI service exposing policies, audits, report comparison and policy diffs.

Run locally: `uvicorn ccauditor.api:app --reload`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
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
# Serverless hosts (Vercel) have no logged-in Claude Code CLI, so LLM modes are downgraded to the
# deterministic rule engine unless CCAUDITOR_ALLOW_LLM=1 is set explicitly.
ALLOW_LLM = os.environ.get("CCAUDITOR_ALLOW_LLM") == "1" or not SERVERLESS


def effective_mode(requested: str | None) -> Literal["deterministic", "llm", "hybrid"]:
    mode = requested or DEFAULT_MODE
    return mode if ALLOW_LLM else "deterministic"  # type: ignore[return-value]


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
    return {"status": "ok", "version": __version__, "default_mode": DEFAULT_MODE, "serverless": SERVERLESS,
            "llm_enabled": ALLOW_LLM}


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


_GITHUB_URL = re.compile(r"^https://(www\.)?github\.com/([\w.-]+)/([\w.-]+?)(\.git)?/?$")
MAX_TARBALL_BYTES = int(os.environ.get("CCAUDITOR_MAX_TARBALL_MB", "200")) * 1024 * 1024


def _github_tarball_url(url: str) -> str | None:
    """https://github.com/<owner>/<repo>[.git] -> codeload tarball URL of the default branch HEAD."""
    m = _GITHUB_URL.match(url)
    if not m:
        return None
    return f"https://codeload.github.com/{m.group(2)}/{m.group(3)}/tar.gz/HEAD"


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract regular files/dirs only, refusing absolute paths, '..' and links outside dest."""
    dest = dest.resolve()
    members = []
    for m in tar.getmembers():
        if not (m.isfile() or m.isdir()):
            continue  # skip symlinks, hardlinks, devices
        target = (dest / m.name).resolve()
        if target != dest and dest not in target.parents:
            continue
        members.append(m)
    if hasattr(tarfile, "data_filter"):
        tar.extractall(dest, members=members, filter="data")
    else:  # pragma: no cover - Python < 3.11.4
        tar.extractall(dest, members=members)


def _download_tarball(url: str, dest: Path) -> None:
    """Fallback for hosts without git (e.g. Vercel functions): fetch the GitHub tarball and unpack it."""
    import httpx

    tar_url = _github_tarball_url(url)
    if tar_url is None:
        raise HTTPException(400, "git is not available on this server; only https://github.com/<owner>/<repo> "
                                 "URLs can be audited (downloaded as a tarball)")
    archive = dest.parent / "repo.tar.gz"
    size = 0
    try:
        with httpx.stream("GET", tar_url, follow_redirects=True, timeout=60) as resp:
            if resp.status_code != 200:
                raise HTTPException(400, f"could not download {tar_url}: HTTP {resp.status_code}")
            with archive.open("wb") as fh:
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_TARBALL_BYTES:
                        raise HTTPException(413, "repository archive is too large")
                    fh.write(chunk)
    except httpx.HTTPError as exc:
        raise HTTPException(400, f"could not download {tar_url}: {exc}") from exc
    unpack = dest.parent / "unpack"
    unpack.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            _safe_extract(tar, unpack)
    except tarfile.TarError as exc:
        raise HTTPException(400, f"invalid repository archive: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)
    roots = [p for p in unpack.iterdir() if p.is_dir()]
    # codeload archives contain a single top-level "<repo>-<sha>/" directory
    (roots[0] if len(roots) == 1 else unpack).rename(dest)


def _clone(url: str, dest: Path) -> None:
    if not _REPO_URL.match(url):
        raise HTTPException(400, "repo_url must be a public https git URL")
    if not shutil.which("git") or os.environ.get("CCAUDITOR_FETCH") == "tarball":
        _download_tarball(url, dest)
        return
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
    mode = effective_mode(req.mode)
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
