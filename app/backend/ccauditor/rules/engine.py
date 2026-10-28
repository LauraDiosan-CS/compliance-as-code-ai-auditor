"""Deterministic evaluation of Requirement.checks against a repository.

Each check yields "pass", "fail" or "unknown". Aggregation per requirement:
all pass -> COMPLIANT, none pass -> NON_COMPLIANT, mixed -> PARTIAL,
no checks / only unknown -> NEEDS_REVIEW. Unknown checks are ignored when others resolved.

Pattern checks run on comment-masked text (comments, docstrings and TODO/FIXME/TBD lines are blanked,
see ``rules.comments``), and "present" checks ignore switched-off feature flags (``x_allowed = False``).

Confidence is graded per check ("strength") rather than fixed per status: many matches across files in
code/config is strong evidence; a single match, a match only in documentation for a technical check
(a claim, not an implementation), a regex that simply did not match (indirect evidence may exist) or an
"absent" check that passed (absence of a pattern) are weak. The hybrid orchestrator routes weak verdicts
to the LLM judge.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml

from ccauditor.evidence.files import iter_repo_files, read_text
from ccauditor.rules.comments import comment_kind, is_disabled_flag_line, mask_non_code
from ccauditor.models import (
    Evidence,
    EvidenceIndex,
    EvidenceKind,
    Requirement,
    RiskLevel,
    RuleCheck,
    Status,
    Verdict,
)

Outcome = Literal["pass", "fail", "unknown"]
MAX_EVIDENCE_PER_CHECK = 5
# Status-level defaults (used for N/A, partial, needs_review and checks without a graded strength)
CONFIDENCE = {
    Status.COMPLIANT: 0.9,
    Status.NON_COMPLIANT: 0.8,
    Status.PARTIAL: 0.5,
    Status.NEEDS_REVIEW: 0.2,
    Status.NOT_APPLICABLE: 0.9,
}
DOC_KINDS = {EvidenceKind.DOC, EvidenceKind.MODEL_CARD}
TECH_KINDS = {EvidenceKind.CODE, EvidenceKind.CONFIG, EvidenceKind.IAC}

# graded strengths (probability-like: how much one check outcome should be trusted on its own)
S_PRESENT_MANY = 0.9        # cap for many hits across files
S_PRESENT_ONE = 0.65        # a single matching line
S_PRESENT_DOC_CLAIM = 0.55  # technical check satisfied only by documentation text
S_PRESENT_COMMENT = 0.55    # satisfied only by an explanatory code comment / docstring (a claim)
S_ABSENT_FOUND = 0.8        # forbidden pattern found in real (non-comment) code
S_ABSENT_CLEAN = 0.6        # forbidden pattern not found (absence of evidence)
S_MISSING = 0.6             # required pattern not found (regexes miss indirect evidence)
S_MISSING_ONLY_COMMENTED = 0.75  # required pattern appears only in comments / TODOs: intent, not implementation
S_MISSING_NO_FILES = 0.8    # nothing of the required kind exists at all
S_FILE_FOUND = 0.7
S_FILE_MISSING = 0.65
S_YAML_FOUND = 0.85
S_YAML_MISSING = 0.65
S_REGO = 0.9


@dataclass
class CheckResult:
    check: RuleCheck
    outcome: Outcome
    message: str
    evidence_ids: list[str] = field(default_factory=list)
    strength: float | None = None  # confidence in this outcome (None -> status default)


class RepoView:
    """Cached access to repo files and the evidence index for one evaluation run."""

    def __init__(self, repo_root: str | Path, index: EvidenceIndex) -> None:
        self.root = Path(repo_root).resolve()
        self.index = index
        self._text: dict[str, str] = {}
        self._masked: dict[str, str] = {}
        self.kind_of: dict[str, EvidenceKind] = {}
        self._chunks: dict[str, list[Evidence]] = {}
        for e in index.items:
            self.kind_of.setdefault(e.path, e.kind)
            self._chunks.setdefault(e.path, []).append(e)
        for chunks in self._chunks.values():
            chunks.sort(key=lambda e: e.start_line)
        self._all_files: list[str] | None = None

    @property
    def indexed_paths(self) -> list[str]:
        return list(self.kind_of)

    @property
    def all_files(self) -> list[str]:
        """Every readable text file, including ones the collector did not classify (e.g. LICENSE)."""
        if self._all_files is None:
            self._all_files = [p.relative_to(self.root).as_posix() for p in iter_repo_files(self.root)]
        return self._all_files

    def text(self, path: str) -> str:
        if path not in self._text:
            self._text[path] = read_text(self.root / path)
        return self._text[path]

    def masked(self, path: str) -> str:
        """File text with comments, docstrings and TODO lines blanked (line numbers preserved)."""
        if path not in self._masked:
            self._masked[path] = mask_non_code(path, self.text(path))
        return self._masked[path]

    def select(self, globs: list[str], kinds: list[EvidenceKind]) -> list[str]:
        paths = self.indexed_paths
        if kinds:
            wanted = {EvidenceKind(k) for k in kinds}
            paths = [p for p in paths if self.kind_of[p] in wanted]
        if globs:
            paths = [p for p in paths if any(glob_match(p, g) for g in globs)]
        return paths

    def evidence_at(self, path: str, line: int) -> str | None:
        """Id of the chunk containing `line` (the one where it is most centred)."""
        best, best_margin = None, -1
        for e in self._chunks.get(path, []):
            if e.start_line <= line <= e.end_line:
                margin = min(line - e.start_line, e.end_line - line)
                if margin > best_margin:
                    best, best_margin = e, margin
        return best.id if best else None

    def first_chunk(self, path: str) -> str | None:
        chunks = self._chunks.get(path)
        return chunks[0].id if chunks else None


def glob_match(rel_path: str, pattern: str) -> bool:
    """fnmatch with '**/' support; patterns without '/' also match the basename."""
    if pattern.startswith("./"):
        pattern = pattern[2:]
    if fnmatch.fnmatch(rel_path, pattern):
        return True
    if pattern.startswith("**/") and glob_match(rel_path, pattern[3:]):
        return True
    if "/**/" in pattern:
        head, tail = pattern.split("/**/", 1)
        if glob_match(rel_path, f"{head}/{tail}"):
            return True
    if "/" not in pattern and fnmatch.fnmatch(PurePosixPath(rel_path).name, pattern):
        return True
    return False


def _describe(check: RuleCheck) -> str:
    if check.description:
        return check.description
    scope = ", ".join([*map(str, check.globs), *(k.value for k in check.kinds)]) or "all files"
    if check.type == "pattern":
        return f"pattern /{check.pattern}/ {check.expect} in {scope}"
    if check.type == "file_exists":
        verb = "exists" if check.expect == "present" else "does not exist"
        return f"a file matching {scope} {verb}"
    if check.type == "yaml_path":
        cond = f" == {check.equals!r}" if check.equals is not None else ""
        return f"key `{check.path}`{cond} {check.expect} in {scope}"
    return "rego policy evaluates to allow"


# ------------------------------------------------------------------ individual checks


def _present_strength(hits: list[tuple[str, int]], view: RepoView, check: RuleCheck) -> float:
    files = {p for p, _ in hits}
    kinds = {view.kind_of.get(p) for p in files}
    technical_scope = not check.kinds or any(EvidenceKind(k) in TECH_KINDS for k in check.kinds)
    if technical_scope and kinds and kinds <= DOC_KINDS:
        return S_PRESENT_DOC_CLAIM
    lines = len(set(hits))
    s = S_PRESENT_ONE + 0.08 * (min(lines, 4) - 1) + (0.05 if len(files) > 1 else 0.0)
    return round(min(S_PRESENT_MANY, s), 3)


def _check_pattern(check: RuleCheck, view: RepoView) -> CheckResult:
    desc = _describe(check)
    if not check.pattern:
        return CheckResult(check, "unknown", f"{desc}: no pattern given")
    try:
        rx = re.compile(check.pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        return CheckResult(check, "unknown", f"{desc}: invalid regex ({exc})")
    hits: list[tuple[str, int]] = []
    ignored: list[tuple[str, int, str]] = []  # (path, line, reason)
    candidates = view.select(check.globs, check.kinds)
    for path in candidates:
        raw = view.text(path)
        masked = view.masked(path)
        lines = raw.splitlines()
        real_lines: set[int] = set()
        for m in rx.finditer(masked):  # matches in actual code / prose
            line = masked.count("\n", 0, m.start()) + 1
            if check.expect == "present" and 0 < line <= len(lines) and is_disabled_flag_line(lines[line - 1]):
                ignored.append((path, line, "disabled flag"))
                continue
            real_lines.add(line)
            if len(hits) < 50:
                hits.append((path, line))
        if masked != raw:  # matches that exist only in comments / docstrings / TODO lines
            for m in rx.finditer(raw):
                line = raw.count("\n", 0, m.start()) + 1
                if line in real_lines or len(ignored) >= 20:
                    continue
                kind = comment_kind(lines[line - 1]) if 0 < line <= len(lines) else "todo"
                ignored.append((path, line, {"todo": "TODO", "code": "commented-out code",
                                             "prose": "comment"}[kind]))
    ev: list[str] = []
    for path, line in hits:
        eid = view.evidence_at(path, line)
        if eid and eid not in ev:
            ev.append(eid)
        if len(ev) >= MAX_EVIDENCE_PER_CHECK:
            break
    where = ", ".join(sorted({f"{p}:{ln}" for p, ln in hits[:5]}))
    note = ""
    if ignored:
        note = " (ignored: " + ", ".join(f"{p}:{ln} [{why}]" for p, ln, why in ignored[:3]) + ")"
    if check.expect == "present":
        if hits:
            s = _present_strength(hits, view, check)
            claim = " - documentation only (claim, not implementation)" if s == S_PRESENT_DOC_CLAIM else ""
            return CheckResult(check, "pass", f"{desc}: found at {where}{claim}{note}", ev, s)
        if not candidates:
            return CheckResult(check, "fail", f"{desc}: no file of the required kind exists", [], S_MISSING_NO_FILES)
        prose = [(p, ln) for p, ln, why in ignored if why == "comment"]
        if prose:  # explanatory comments / docstrings describe behaviour: a weak claim, not proof
            ev_c = list(dict.fromkeys(eid for p, ln in prose[:MAX_EVIDENCE_PER_CHECK]
                                      if (eid := view.evidence_at(p, ln))))
            where_c = ", ".join(sorted({f"{p}:{ln}" for p, ln in prose[:5]}))
            return CheckResult(check, "pass", f"{desc}: only in explanatory comments/docstrings at {where_c} "
                               f"(claim, verify the code){note}", ev_c, S_PRESENT_COMMENT)
        if ignored:
            ign_ev = [eid for p, ln, _ in ignored[:MAX_EVIDENCE_PER_CHECK] if (eid := view.evidence_at(p, ln))]
            return CheckResult(check, "fail", f"{desc}: only commented-out / TODO / disabled matches{note}",
                               list(dict.fromkeys(ign_ev)), S_MISSING_ONLY_COMMENTED)
        return CheckResult(check, "fail", f"{desc}: no match found", [], S_MISSING)
    if hits:
        return CheckResult(check, "fail", f"{desc}: forbidden pattern found at {where}", ev, S_ABSENT_FOUND)
    return CheckResult(check, "pass", f"{desc}: confirmed absent{note}", [], S_ABSENT_CLEAN)


def _check_file_exists(check: RuleCheck, view: RepoView) -> CheckResult:
    desc = _describe(check)
    if not check.globs:
        return CheckResult(check, "unknown", f"{desc}: no globs given")
    files = view.all_files
    if check.kinds:
        files = view.select([], check.kinds)
    matches = [p for p in files if any(glob_match(p, g) for g in check.globs)]
    ev = [eid for p in matches[:MAX_EVIDENCE_PER_CHECK] if (eid := view.first_chunk(p))]
    if check.expect == "present":
        if matches:
            return CheckResult(check, "pass", f"{desc}: found {', '.join(matches[:5])}", ev, S_FILE_FOUND)
        return CheckResult(check, "fail", f"{desc}: no matching file", [], S_FILE_MISSING)
    if matches:
        return CheckResult(check, "fail", f"{desc}: unexpected file(s) {', '.join(matches[:5])}", ev, S_FILE_FOUND)
    return CheckResult(check, "pass", f"{desc}: confirmed absent", [], S_FILE_MISSING)


_MISSING = object()


def _lookup(doc: Any, keys: list[str]) -> list[Any]:
    """Resolve a dot path; '*' fans out over dict values / list items; digits index lists."""
    if not keys:
        return [doc]
    key, rest = keys[0], keys[1:]
    out: list[Any] = []
    if key == "*":
        children = doc.values() if isinstance(doc, dict) else doc if isinstance(doc, list) else []
        for c in children:
            out.extend(_lookup(c, rest))
    elif isinstance(doc, dict) and key in doc:
        out.extend(_lookup(doc[key], rest))
    elif isinstance(doc, list):
        if key.isdigit() and int(key) < len(doc):
            out.extend(_lookup(doc[int(key)], rest))
        else:  # implicit fan-out over list of mappings
            for c in doc:
                if isinstance(c, dict) and key in c:
                    out.extend(_lookup(c[key], rest))
    return out


def _load_docs(path: str, text: str) -> list[Any]:
    try:
        if path.endswith(".json"):
            return [json.loads(text)]
        if path.endswith(".toml"):
            import tomllib

            return [tomllib.loads(text)]
        return [d for d in yaml.safe_load_all(text) if d is not None]
    except Exception:  # noqa: BLE001 - malformed files are simply skipped
        return []


def _equals(value: Any, expected: Any) -> bool:
    if value == expected:
        return True
    return str(value).strip().lower() == str(expected).strip().lower()


def _check_yaml_path(check: RuleCheck, view: RepoView) -> CheckResult:
    desc = _describe(check)
    if not check.path:
        return CheckResult(check, "unknown", f"{desc}: no path given")
    keys = check.path.split(".")
    candidates = view.select(check.globs, check.kinds)
    candidates = [p for p in candidates if PurePosixPath(p).suffix.lower() in (".yaml", ".yml", ".json", ".toml")]
    found: list[tuple[str, Any]] = []
    for path in candidates:
        for doc in _load_docs(path, view.text(path)):
            for val in _lookup(doc, keys):
                if check.equals is None or _equals(val, check.equals):
                    found.append((path, val))
    ev: list[str] = []
    for path, _ in found:
        text = view.text(path)
        m = re.search(rf"^\s*-?\s*[\"']?{re.escape(keys[-1])}[\"']?\s*[:=]", text, re.MULTILINE)
        line = text.count("\n", 0, m.start()) + 1 if m else 1
        eid = view.evidence_at(path, line) or view.first_chunk(path)
        if eid and eid not in ev:
            ev.append(eid)
        if len(ev) >= MAX_EVIDENCE_PER_CHECK:
            break
    where = ", ".join(sorted({p for p, _ in found})[:5])
    if check.expect == "present":
        if found:
            return CheckResult(check, "pass", f"{desc}: found in {where}", ev, S_YAML_FOUND)
        return CheckResult(check, "fail", f"{desc}: not found in {len(candidates)} candidate file(s)", [],
                           S_YAML_MISSING)
    if found:
        return CheckResult(check, "fail", f"{desc}: present in {where}", ev, S_YAML_FOUND)
    return CheckResult(check, "pass", f"{desc}: confirmed absent", [], S_YAML_MISSING)


def _check_rego(check: RuleCheck, view: RepoView) -> CheckResult:
    desc = _describe(check)
    opa = shutil.which("opa")
    if not check.rego:
        return CheckResult(check, "unknown", f"{desc}: no rego policy given")
    if not opa:
        return CheckResult(check, "unknown", f"{desc}: OPA not installed, check skipped")
    m = re.search(r"^\s*package\s+([\w.]+)", check.rego, re.MULTILINE)
    pkg = m.group(1) if m else "ccauditor"
    rego = check.rego if m else f"package ccauditor\n{check.rego}"
    configs: dict[str, list[Any]] = {}
    for path in view.select(check.globs, check.kinds or [EvidenceKind.CONFIG, EvidenceKind.IAC]):
        if PurePosixPath(path).suffix.lower() in (".yaml", ".yml", ".json"):
            configs[path] = _load_docs(path, view.text(path))
    payload = {"files": view.indexed_paths, "configs": configs}
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "policy.rego").write_text(rego)
        (Path(tmp) / "input.json").write_text(json.dumps(payload, default=str))
        try:
            proc = subprocess.run(
                [opa, "eval", "--format", "json", "-d", str(Path(tmp) / "policy.rego"),
                 "-i", str(Path(tmp) / "input.json"), f"data.{pkg}.allow"],
                capture_output=True, text=True, timeout=30,
            )
            result = json.loads(proc.stdout or "{}")
            value = result["result"][0]["expressions"][0]["value"]
        except Exception as exc:  # noqa: BLE001
            return CheckResult(check, "unknown", f"{desc}: OPA evaluation failed ({exc})")
    allowed = value is True
    if check.expect == "absent":
        allowed = not allowed
    return CheckResult(check, "pass" if allowed else "fail", f"{desc}: OPA returned allow={value}", [], S_REGO)


_CHECKERS = {
    "pattern": _check_pattern,
    "file_exists": _check_file_exists,
    "yaml_path": _check_yaml_path,
    "rego": _check_rego,
}


def run_check(check: RuleCheck, view: RepoView) -> CheckResult:
    return _CHECKERS[check.type](check, view)


# ------------------------------------------------------------------ aggregation


def graded_confidence(status: Status, results: list[CheckResult]) -> float:
    """Confidence of the aggregated verdict from the strengths of the checks that decided it.

    compliant -> mean strength of passing checks; non_compliant -> mean strength of failing checks;
    +0.05 when two or more independent checks agree. partial / needs_review keep their status default.
    """
    if status == Status.COMPLIANT:
        decisive = [r for r in results if r.outcome == "pass"]
    elif status == Status.NON_COMPLIANT:
        decisive = [r for r in results if r.outcome == "fail"]
    else:
        return CONFIDENCE[status]
    vals = [r.strength if r.strength is not None else CONFIDENCE[status] for r in decisive]
    if not vals:
        return CONFIDENCE[status]
    conf = sum(vals) / len(vals) + (0.05 if len(vals) >= 2 else 0.0)
    return round(min(0.95, conf), 3)


def aggregate(results: list[CheckResult]) -> Status:
    resolved = [r for r in results if r.outcome != "unknown"]
    if not resolved:
        return Status.NEEDS_REVIEW
    passed = sum(r.outcome == "pass" for r in resolved)
    if passed == len(resolved):
        return Status.COMPLIANT
    if passed == 0:
        return Status.NON_COMPLIANT
    return Status.PARTIAL


_LAST_VIEW: tuple[EvidenceIndex, RepoView] | None = None


def _cached_view(repo_root: str | Path, index: EvidenceIndex) -> RepoView:
    """Reuse the view across per-requirement calls on the same index (pipeline calls us in a loop)."""
    global _LAST_VIEW
    root = Path(repo_root).resolve()
    if _LAST_VIEW and _LAST_VIEW[0] is index and _LAST_VIEW[1].root == root:
        return _LAST_VIEW[1]
    view = RepoView(root, index)
    _LAST_VIEW = (index, view)
    return view


def evaluate_requirement(
    req: Requirement, repo_root: str | Path, index: EvidenceIndex, view: RepoView | None = None
) -> Verdict:
    view = view or _cached_view(repo_root, index)
    results = [run_check(c, view) for c in req.checks]
    status = aggregate(results)

    evidence_ids: list[str] = []
    for r in results:
        for eid in r.evidence_ids:
            if eid not in evidence_ids:
                evidence_ids.append(eid)

    if not results:
        rationale = "No deterministic checks defined for this requirement; human or LLM review needed."
    else:
        lines = [f"- [{r.outcome.upper()}{'' if r.strength is None else f' {r.strength:.2f}'}] {r.message}"
                 for r in results]
        n_pass = sum(r.outcome == "pass" for r in results)
        n_unknown = sum(r.outcome == "unknown" for r in results)
        rationale = f"{n_pass}/{len(results)} deterministic checks passed"
        if n_unknown:
            rationale += f" ({n_unknown} could not be evaluated)"
        rationale += ".\n" + "\n".join(lines)

    gaps = [_describe(r.check) for r in results if r.outcome == "fail"]
    if status == Status.NEEDS_REVIEW and not gaps:
        gaps = ["Automated checks inconclusive; manual verification required."]
    remediation = ""
    if status in (Status.NON_COMPLIANT, Status.PARTIAL):
        remediation = f"To satisfy '{req.title}': {req.statement} Missing: " + "; ".join(gaps) + "."

    return Verdict(
        requirement_id=req.id,
        status=status,
        confidence=graded_confidence(status, results),
        rationale=rationale,
        evidence_ids=evidence_ids,
        gaps=gaps,
        remediation=remediation,
        method="deterministic",
    )


def _risk(level: RiskLevel | str | None) -> RiskLevel | None:
    if level is None:
        return None
    level = RiskLevel(level)
    return None if level == RiskLevel.UNKNOWN else level


def evaluate_all(
    requirements: list[Requirement],
    repo_root: str | Path,
    index: EvidenceIndex,
    risk_level: RiskLevel | str | None = None,
) -> list[Verdict]:
    """Evaluate every requirement; NOT_APPLICABLE when a known risk level is outside applies_to."""
    view = RepoView(repo_root, index)
    risk = _risk(risk_level)
    verdicts: list[Verdict] = []
    for req in requirements:
        if risk is not None and req.applies_to and risk not in req.applies_to:
            verdicts.append(
                Verdict(
                    requirement_id=req.id,
                    status=Status.NOT_APPLICABLE,
                    confidence=CONFIDENCE[Status.NOT_APPLICABLE],
                    rationale=f"Applies to {', '.join(r.value for r in req.applies_to)} risk systems; "
                    f"this system is classified as {risk.value}.",
                    method="deterministic",
                )
            )
            continue
        verdicts.append(evaluate_requirement(req, repo_root, index, view=view))
    return verdicts
