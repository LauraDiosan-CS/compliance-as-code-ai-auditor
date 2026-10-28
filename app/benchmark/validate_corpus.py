"""Validate the bundled policy corpora, curated requirements and benchmark ground truth.

Run from the repo root:  .venv/bin/python app/benchmark/validate_corpus.py

Checks:
  * every policy markdown parses with ccauditor.policies.loader.load_policy (unique clause ids);
  * every requirements YAML validates against ccauditor.models.Requirement (via load_requirements),
    requirement ids are unique, and every clause_id exists in the corresponding policy;
  * every regex in pattern checks compiles with re.IGNORECASE | re.MULTILINE;
  * every ground-truth file labels every requirement with a valid Status, and labels requirements
    whose applies_to excludes the app's risk level as not_applicable (and only those).
Exit code 1 on any error.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from ccauditor.models import RiskLevel, Status  # noqa: E402
from ccauditor.policies.loader import load_policy, load_requirements  # noqa: E402

DATA = ROOT / "app" / "backend" / "ccauditor" / "data"
BENCH = ROOT / "app" / "benchmark"

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print("ERROR:", msg)


def main() -> int:
    # ---------------------------------------------------------------- policies
    clauses_by_policy: dict[str, set[str]] = {}
    for f in sorted((DATA / "policies").glob("*.md")):
        p = load_policy(f)
        ids = [c.id for c in p.clauses]
        dup = [i for i, n in Counter(ids).items() if n > 1]
        if dup:
            err(f"{f.name}: duplicate clause ids {dup}")
        if not ids:
            err(f"{f.name}: no clauses parsed")
        for c in p.clauses:
            if c.parent_id is not None and not c.text.strip():
                err(f"{f.name}: clause {c.id} has empty text")
        print(f"policy {f.name:42s} id={p.id:10s} v={p.version:11s} clauses={len(ids)}")
        # v1 file (or the one named after the id) defines the canonical clause set
        clauses_by_policy.setdefault(p.id, set(ids))

    # ---------------------------------------------------------------- requirements
    all_reqs = {}
    for f in sorted((DATA / "requirements").glob("*.y*ml")):
        reqs = load_requirements(f)
        for r in reqs:
            if r.id in all_reqs:
                err(f"{f.name}: duplicate requirement id {r.id}")
            all_reqs[r.id] = r
            known = clauses_by_policy.get(r.policy_id)
            if known is None:
                err(f"{f.name}:{r.id}: unknown policy_id {r.policy_id}")
                continue
            for cid in r.clause_ids:
                if cid not in known:
                    err(f"{f.name}:{r.id}: clause_id {cid!r} not found in policy {r.policy_id}")
            for i, chk in enumerate(r.checks):
                if chk.type == "pattern":
                    if not chk.pattern:
                        err(f"{r.id} check {i}: pattern missing")
                        continue
                    try:
                        re.compile(chk.pattern, re.IGNORECASE | re.MULTILINE)
                    except re.error as exc:
                        err(f"{r.id} check {i}: invalid regex {chk.pattern!r}: {exc}")
                if chk.type == "file_exists" and not chk.globs:
                    err(f"{r.id} check {i}: file_exists without globs")
                if chk.type == "yaml_path" and not chk.path:
                    err(f"{r.id} check {i}: yaml_path without path")
            if not r.evidence_queries:
                err(f"{r.id}: no evidence_queries")
        n_checks = sum(len(r.checks) for r in reqs)
        n_llm = sum(1 for r in reqs if not r.checks)
        print(f"requirements {f.name:20s} n={len(reqs):3d} checks={n_checks:3d} llm-only={n_llm}")

    # ---------------------------------------------------------------- ground truth
    gt_dir = BENCH / "ground_truth"
    apps_dir = BENCH / "apps"
    for f in sorted(gt_dir.glob("*.json")) if gt_dir.is_dir() else []:
        gt = json.loads(f.read_text())
        app = gt.get("app")
        if not (apps_dir / str(app)).is_dir():
            err(f"{f.name}: app dir {app} missing")
        try:
            risk = RiskLevel(gt["risk_level"])
        except Exception:  # noqa: BLE001
            err(f"{f.name}: invalid risk_level {gt.get('risk_level')}")
            continue
        labels = gt.get("labels", {})
        notes = gt.get("notes", {})
        missing = sorted(set(all_reqs) - set(labels))
        extra = sorted(set(labels) - set(all_reqs))
        if missing:
            err(f"{f.name}: missing labels for {missing}")
        if extra:
            err(f"{f.name}: labels for unknown requirements {extra}")
        for rid, status in labels.items():
            try:
                st = Status(status)
            except ValueError:
                err(f"{f.name}:{rid}: invalid status {status}")
                continue
            req = all_reqs.get(rid)
            if req is None:
                continue
            applicable = risk in req.applies_to
            if not applicable and st != Status.NOT_APPLICABLE:
                err(f"{f.name}:{rid}: applies_to excludes {risk.value} but label is {st.value}")
            if applicable and st == Status.NOT_APPLICABLE:
                err(f"{f.name}:{rid}: applicable to {risk.value} but labelled not_applicable")
            if applicable and not notes.get(rid):
                err(f"{f.name}:{rid}: missing justification note")
        print(f"ground truth {f.name:32s} risk={risk.value:8s} " + str(dict(Counter(labels.values()))))

    print(f"\n{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
