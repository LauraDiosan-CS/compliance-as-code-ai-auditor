"""Load policy markdown files and curated requirement YAML files.

Policy markdown format (see docs/design/ARCHITECTURE.md)::

    ---
    id: eu-ai-act
    name: EU AI Act
    version: "2024-07-12"
    kind: regulation
    source: https://...
    ---
    ## Art. 12 | Record-keeping       -> clause "<id>/Art.12"
    ### 1                             -> clause "<id>/Art.12(1)" (parent "<id>/Art.12")
    text...
    ## Annex III | High-risk areas    -> clause "<id>/AnnexIII"
    ### 4(a)                          -> clause "<id>/AnnexIII(4)(a)"
    ## POL-3 | Data retention         -> clause "<id>/POL-3"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ccauditor.models import Clause, Policy, Requirement

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLICIES_DIR = DATA_DIR / "policies"
REQUIREMENTS_DIR = DATA_DIR / "requirements"

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3 = re.compile(r"^###\s+(?!#)(.+?)\s*$")


def _normalize_ref(ref: str) -> str:
    """'Art. 12' -> 'Art.12', 'Annex III' -> 'AnnexIII', 'POL-3' -> 'POL-3'."""
    ref = ref.strip()
    m = re.match(r"^(Art(?:icle)?)\.?\s*(\S+)$", ref, re.IGNORECASE)
    if m:
        return f"Art.{m.group(2)}"
    m = re.match(r"^Annex\s+(\S+)$", ref, re.IGNORECASE)
    if m:
        return f"Annex{m.group(1)}"
    return re.sub(r"\s+", "", ref)


def _normalize_sub(sub: str) -> str:
    """'1' -> '(1)', '4(a)' -> '(4)(a)', '(2)' -> '(2)', 'a' -> '(a)'."""
    sub = sub.strip().rstrip(".")
    if not sub:
        return ""
    parts = re.findall(r"[^()\s]+", sub)
    return "".join(f"({p})" for p in parts)


def _split_heading(text: str) -> tuple[str, str]:
    if "|" in text:
        ref, title = text.split("|", 1)
        return ref.strip(), title.strip()
    return text.strip(), ""


def parse_policy_markdown(content: str, source: str = "") -> Policy:
    """Parse policy markdown text into a Policy with hierarchical clauses."""
    meta: dict[str, Any] = {}
    body = content
    m = _FRONT_MATTER.match(content)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body = content[m.end():]
    policy_id = str(meta.get("id") or Path(source).stem or "policy")

    clauses: list[Clause] = []
    current_parent: Clause | None = None
    current: Clause | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            current.text = "\n".join(buffer).strip()
        buffer.clear()

    for line in body.splitlines():
        h2 = _H2.match(line)
        h3 = _H3.match(line)
        if h2:
            flush()
            ref, title = _split_heading(h2.group(1))
            current_parent = Clause(
                id=f"{policy_id}/{_normalize_ref(ref)}", policy_id=policy_id, title=title, text=""
            )
            clauses.append(current_parent)
            current = current_parent
        elif h3 and current_parent is not None:
            flush()
            ref, title = _split_heading(h3.group(1))
            cid = f"{current_parent.id}{_normalize_sub(ref)}"
            # "### 4(a)" nests under an existing "### 4" sibling when present
            parent_id = current_parent.id
            known = {c.id for c in clauses}
            prefix = cid
            while "(" in prefix[len(current_parent.id):]:
                prefix = prefix[: prefix.rfind("(")]
                if prefix in known:
                    parent_id = prefix
                    break
            current = Clause(
                id=cid,
                policy_id=policy_id,
                title=title or current_parent.title,
                text="",
                parent_id=parent_id,
            )
            clauses.append(current)
        else:
            buffer.append(line)
    flush()

    kind = meta.get("kind", "regulation")
    if kind not in ("regulation", "internal_policy", "control_framework"):
        kind = "regulation"
    return Policy(
        id=policy_id,
        name=str(meta.get("name", policy_id)),
        version=str(meta.get("version", "1")),
        source=str(meta.get("source", source)),
        kind=kind,
        clauses=clauses,
    )


def load_policy(path: str | Path) -> Policy:
    path = Path(path)
    return parse_policy_markdown(path.read_text(encoding="utf-8"), source=str(path))


def parse_requirements_yaml(content: str) -> list[Requirement]:
    data = yaml.safe_load(content) or {}
    if isinstance(data, list):
        data = {"requirements": data}
    policy_id = data.get("policy_id", "")
    reqs: list[Requirement] = []
    for raw in data.get("requirements") or []:
        raw = dict(raw)
        raw.setdefault("policy_id", policy_id)
        reqs.append(Requirement.model_validate(raw))
    return reqs


def load_requirements(path: str | Path) -> list[Requirement]:
    return parse_requirements_yaml(Path(path).read_text(encoding="utf-8"))


def _requirements_policy_id(path: Path) -> str | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data.get("policy_id") if isinstance(data, dict) else None


def _requirements_files(policy_id: str, requirements_dir: Path) -> list[Path]:
    if not requirements_dir.is_dir():
        return []
    files = sorted(requirements_dir.glob("*.y*ml"))
    return [f for f in files if _requirements_policy_id(f) == policy_id]


def list_builtin_policies(
    policies_dir: Path | None = None, requirements_dir: Path | None = None
) -> list[dict[str, Any]]:
    """Summaries of bundled policies: id, name, version, kind, source, file, clause/requirement counts."""
    policies_dir = policies_dir or POLICIES_DIR
    requirements_dir = requirements_dir or REQUIREMENTS_DIR
    out: list[dict[str, Any]] = []
    if not policies_dir.is_dir():
        return out
    for f in sorted(policies_dir.glob("*.md")):
        try:
            policy = load_policy(f)
        except Exception:  # noqa: BLE001 - a broken corpus file must not break listing
            continue
        req_files = _requirements_files(policy.id, requirements_dir)
        n_reqs = sum(len(load_requirements(r)) for r in req_files)
        out.append(
            {
                "id": policy.id,
                "name": policy.name,
                "version": policy.version,
                "kind": policy.kind,
                "source": policy.source,
                "file": str(f),
                "clauses": len(policy.clauses),
                "requirements": n_reqs,
                "requirements_files": [str(r) for r in req_files],
            }
        )
    return out


def _policy_file(policy_id: str, policies_dir: Path) -> Path | None:
    for f in sorted(policies_dir.glob("*.md")):
        if f.stem == policy_id:
            return f
    for f in sorted(policies_dir.glob("*.md")):
        m = _FRONT_MATTER.match(f.read_text(encoding="utf-8"))
        if m and str((yaml.safe_load(m.group(1)) or {}).get("id")) == policy_id:
            return f
    return None


def get_policy(policy_id: str, policies_dir: Path | None = None) -> Policy:
    """Load a bundled policy by id. Raises KeyError if unknown."""
    d = policies_dir or POLICIES_DIR
    f = _policy_file(policy_id, d) if d.is_dir() else None
    if f is None:
        raise KeyError(f"Unknown policy: {policy_id}")
    return load_policy(f)


def get_requirements(policy_id: str, requirements_dir: Path | None = None) -> list[Requirement]:
    """Curated requirements for a bundled policy (empty list if none)."""
    reqs: list[Requirement] = []
    for f in _requirements_files(policy_id, requirements_dir or REQUIREMENTS_DIR):
        reqs.extend(load_requirements(f))
    return reqs
