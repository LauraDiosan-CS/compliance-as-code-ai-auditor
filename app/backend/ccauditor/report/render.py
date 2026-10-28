"""Render an AuditReport as JSON, Markdown, SARIF 2.1.0 or a standalone HTML page."""

from __future__ import annotations

import html
import json
from pathlib import Path, PurePosixPath
from typing import Any

from ccauditor import __version__
from ccauditor.models import AuditReport, Evidence, Requirement, Status, Verdict

SNIPPET_MAX_LINES = 15
STATUS_LABEL = {
    Status.COMPLIANT: "COMPLIANT",
    Status.NON_COMPLIANT: "NON-COMPLIANT",
    Status.PARTIAL: "PARTIAL",
    Status.NEEDS_REVIEW: "NEEDS REVIEW",
    Status.NOT_APPLICABLE: "N/A",
}
_LANG = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "jsx",
    ".java": "java", ".go": "go", ".rs": "rust", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".toml": "toml", ".tf": "hcl", ".md": "markdown", ".sh": "bash", ".sql": "sql", ".rego": "rego",
}
_STATUS_ORDER = [Status.NON_COMPLIANT, Status.PARTIAL, Status.NEEDS_REVIEW, Status.COMPLIANT, Status.NOT_APPLICABLE]


def to_json(report: AuditReport, indent: int = 2) -> str:
    return report.model_dump_json(indent=indent)


def _cite(e: Evidence) -> str:
    return f"{e.path}:L{e.start_line}-L{e.end_line}"


def _trim(snippet: str, max_lines: int = SNIPPET_MAX_LINES) -> str:
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return snippet
    return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"


def _pairs(report: AuditReport) -> list[tuple[Requirement, Verdict | None]]:
    by_req = {v.requirement_id: v for v in report.verdicts}
    return [(r, by_req.get(r.id)) for r in report.requirements]


def _counts(report: AuditReport) -> dict[Status, int]:
    counts = {s: 0 for s in Status}
    for v in report.verdicts:
        counts[v.status] += 1
    return counts


# ------------------------------------------------------------------ markdown


def to_markdown(report: AuditReport) -> str:
    ev = {e.id: e for e in report.evidence}
    out: list[str] = []
    add = out.append
    add("# Compliance Audit Report")
    add("")
    add(f"- **Target:** `{report.target}`")
    add(f"- **Policies:** {', '.join(report.policies)}")
    add(f"- **Mode:** {report.mode}")
    add(f"- **Generated:** {report.created_at.isoformat(timespec='seconds')}")
    add(f"- **Report id:** `{report.id}`")
    if report.risk:
        add(f"- **Risk level:** {report.risk.level.value.upper()} (confidence {report.risk.confidence:.2f})")
    add(f"- **Overall score:** {report.overall_score:.1f} / 100")
    counts = _counts(report)
    add("- **Verdicts:** " + ", ".join(f"{STATUS_LABEL[s]} {counts[s]}" for s in _STATUS_ORDER if counts[s]))
    add("")

    if report.risk:
        add("## Risk classification")
        add("")
        add(report.risk.rationale)
        for t in report.risk.triggers:
            add(f"- {t}")
        add("")

    if report.scorecard:
        add("## Scorecard")
        add("")
        add("| Category | Score | Compliant | Partial | Non-compliant | Needs review | Total |")
        add("|---|---:|---:|---:|---:|---:|---:|")
        for c in report.scorecard:
            add(
                f"| {c.category.value} | {c.score:.1f} | {c.compliant} | {c.partial} | "
                f"{c.non_compliant} | {c.needs_review} | {c.total} |"
            )
        add("")

    add("## Findings")
    add("")
    pairs = sorted(
        _pairs(report),
        key=lambda rv: (_STATUS_ORDER.index(rv[1].status) if rv[1] else 2, rv[0].id),
    )
    for req, v in pairs:
        status = STATUS_LABEL[v.status] if v else "NOT EVALUATED"
        add(f"### [{status}] {req.id}: {req.title}")
        add("")
        add(f"- **Category:** {req.category.value} | **Severity:** {req.severity}")
        add(f"- **Clauses:** {', '.join(req.clause_ids) or '-'}")
        if v:
            add(f"- **Method:** {v.method} | **Confidence:** {v.confidence:.2f}"
                + (" | citations verified" if v.verified else ""))
        add("")
        add(f"> {req.statement}")
        add("")
        if not v:
            continue
        add("**Rationale**")
        add("")
        add(v.rationale)
        add("")
        cited = [ev[i] for i in v.evidence_ids if i in ev]
        if cited:
            add("**Evidence**")
            add("")
            for e in cited:
                add(f"- `{_cite(e)}` ({e.kind.value}{', ' + e.signal if e.signal else ''})")
                add("")
                lang = _LANG.get(PurePosixPath(e.path).suffix.lower(), "")
                add(f"```{lang}")
                add(_trim(e.snippet))
                add("```")
                add("")
        if v.gaps:
            add("**Gaps**")
            add("")
            for g in v.gaps:
                add(f"- {g}")
            add("")
        if v.remediation:
            add("**Remediation**")
            add("")
            add(v.remediation)
            add("")

    review = [(r, v) for r, v in _pairs(report) if v and v.status == Status.NEEDS_REVIEW]
    add("## Needs human review")
    add("")
    if review:
        for r, v in review:
            reason = v.gaps[0] if v.gaps else "low confidence"
            add(f"- **{r.id}** {r.title} (confidence {v.confidence:.2f}): {reason}")
    else:
        add("No requirements are waiting for human review.")
    add("")
    if report.stats:
        add("## Run statistics")
        add("")
        for k, val in report.stats.items():
            text = val if isinstance(val, str) else json.dumps(val, default=str)
            add(f"- {k}: {text if len(text) <= 200 else text[:197] + '...'}")
        add("")
    return "\n".join(out)


# ------------------------------------------------------------------ SARIF


_SARIF_LEVEL = {Status.NON_COMPLIANT: "error", Status.PARTIAL: "warning", Status.NEEDS_REVIEW: "note"}
_SEVERITY_SCORE = {"critical": "9.0", "high": "7.0", "medium": "5.0", "low": "2.0"}


def _readme_uri(target: str) -> str:
    root = Path(target)
    if root.is_dir():
        for name in sorted(p.name for p in root.iterdir()):
            if name.lower().startswith("readme"):
                return name
    return "README.md"


def to_sarif_dict(report: AuditReport) -> dict[str, Any]:
    ev = {e.id: e for e in report.evidence}
    rules = []
    rule_index: dict[str, int] = {}
    for i, req in enumerate(report.requirements):
        rule_index[req.id] = i
        rules.append(
            {
                "id": req.id,
                "name": req.title.title().replace(" ", ""),
                "shortDescription": {"text": req.title},
                "fullDescription": {"text": req.statement},
                "help": {"text": req.llm_guidance or req.statement},
                "defaultConfiguration": {
                    "level": "error" if req.severity in ("critical", "high") else "warning"
                },
                "properties": {
                    "category": req.category.value,
                    "clause_ids": req.clause_ids,
                    "policy_id": req.policy_id,
                    "severity": req.severity,
                    "security-severity": _SEVERITY_SCORE[req.severity],
                    "tags": ["compliance", req.policy_id, req.category.value],
                },
            }
        )

    readme = _readme_uri(report.target)
    results = []
    for req, v in _pairs(report):
        if not v or v.status not in _SARIF_LEVEL:
            continue
        cited = [ev[i] for i in v.evidence_ids if i in ev]
        if cited:
            locations = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": e.path, "uriBaseId": "SRCROOT"},
                        "region": {"startLine": e.start_line, "endLine": e.end_line},
                    }
                }
                for e in cited[:5]
            ]
        else:
            locations = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": readme, "uriBaseId": "SRCROOT"},
                        "region": {"startLine": 1},
                    }
                }
            ]
        gaps = "; ".join(v.gaps)
        text = f"[{STATUS_LABEL[v.status]}] {req.title}." + (f" Gaps: {gaps}" if gaps else "")
        results.append(
            {
                "ruleId": req.id,
                "ruleIndex": rule_index[req.id],
                "level": _SARIF_LEVEL[v.status],
                "message": {"text": text},
                "locations": locations,
                "properties": {
                    "status": v.status.value,
                    "confidence": v.confidence,
                    "method": v.method,
                    "category": req.category.value,
                    "clause_ids": req.clause_ids,
                    "remediation": v.remediation,
                },
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ccauditor",
                        "fullName": "Compliance-as-Code AI Auditor",
                        "version": __version__,
                        "informationUri": "https://github.com/",
                        "rules": rules,
                    }
                },
                "originalUriBaseIds": {"SRCROOT": {"uri": Path(report.target).resolve().as_uri() + "/"}}
                if Path(report.target).exists()
                else {},
                "results": results,
                "properties": {
                    "report_id": report.id,
                    "policies": report.policies,
                    "overall_score": report.overall_score,
                    "risk_level": report.risk.level.value if report.risk else None,
                },
            }
        ],
    }


def to_sarif(report: AuditReport) -> str:
    return json.dumps(to_sarif_dict(report), indent=2)


# ------------------------------------------------------------------ HTML (minimal, self-contained)


def to_html(report: AuditReport) -> str:
    esc = html.escape
    ev = {e.id: e for e in report.evidence}
    rows = "".join(
        f"<tr><td>{esc(c.category.value)}</td><td>{c.score:.1f}</td><td>{c.compliant}</td>"
        f"<td>{c.partial}</td><td>{c.non_compliant}</td><td>{c.needs_review}</td></tr>"
        for c in report.scorecard
    )
    cards = []
    for req, v in _pairs(report):
        status = STATUS_LABEL[v.status] if v else "NOT EVALUATED"
        evidence = "".join(
            f"<p><code>{esc(_cite(ev[i]))}</code></p><pre>{esc(_trim(ev[i].snippet))}</pre>"
            for i in (v.evidence_ids if v else [])
            if i in ev
        )
        gaps = "".join(f"<li>{esc(g)}</li>" for g in (v.gaps if v else []))
        cards.append(
            f"<section class='{v.status.value if v else ''}'><h3>[{status}] {esc(req.id)}: {esc(req.title)}</h3>"
            f"<p><em>{esc(', '.join(req.clause_ids))}</em></p><p>{esc(req.statement)}</p>"
            f"<pre>{esc(v.rationale if v else '')}</pre>{evidence}"
            + (f"<ul>{gaps}</ul>" if gaps else "")
            + (f"<p><strong>Remediation:</strong> {esc(v.remediation)}</p>" if v and v.remediation else "")
            + "</section>"
        )
    risk = f"<p>Risk level: <strong>{esc(report.risk.level.value)}</strong></p>" if report.risk else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Compliance Audit Report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px}}
pre{{background:#f5f5f5;padding:8px;overflow:auto}}section{{border-left:4px solid #999;padding-left:12px;margin:1rem 0}}
.compliant{{border-color:#2a7}}.non_compliant{{border-color:#c33}}.partial{{border-color:#d90}}.needs_review{{border-color:#36c}}</style>
</head><body><h1>Compliance Audit Report</h1>
<p>Target: <code>{esc(report.target)}</code> | Policies: {esc(', '.join(report.policies))} | Mode: {report.mode}</p>
{risk}<p>Overall score: <strong>{report.overall_score:.1f}</strong> / 100</p>
<table><tr><th>Category</th><th>Score</th><th>Compliant</th><th>Partial</th><th>Non-compliant</th><th>Needs review</th></tr>{rows}</table>
{''.join(cards)}</body></html>"""
