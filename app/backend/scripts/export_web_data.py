"""Export real data for the web dashboard (app/web/public).

* policies/index.json   {generated_at, policies: [{id, name, version, kind, source, clauses, requirements}]}
                        from the bundled corpus (curated requirements for eu-ai-act, gdpr, acme-rai)
* reports/<app>-hybrid.json + reports/index.json
                        one hybrid report per benchmark app, taken from an evaluation run
                        (app/benchmark/results/<run>/reports/<app>__<config>.json)

    .venv/bin/python app/backend/scripts/export_web_data.py --run v1_improved --config hybrid-sonnet
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ccauditor.policies.loader import get_policy, get_requirements

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "app" / "web" / "public"
RESULTS = ROOT / "app" / "benchmark" / "results"
POLICY_IDS = ["eu-ai-act", "gdpr", "acme-rai"]
HAND_MADE = ["talentlens-screening-2026-10-27.json", "northwind-support-bot-2026-10-25.json"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def export_policies() -> Path:
    policies = []
    for pid in POLICY_IDS:
        pol = get_policy(pid)
        reqs = get_requirements(pid)
        d = json.loads(pol.model_dump_json())
        d["requirements"] = [json.loads(r.model_dump_json()) for r in reqs]
        policies.append(d)
    out = WEB / "policies" / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated_at": now(), "policies": policies}, indent=1, ensure_ascii=False) + "\n")
    return out


def export_reports(run: str, config: str) -> Path:
    src_dir = RESULTS / run / "reports"
    files = sorted(src_dir.glob(f"*__{config}.json"))
    if not files:
        raise SystemExit(f"no reports for config {config!r} in {src_dir}")
    rep_dir = WEB / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    entries, ids = [], set()
    for f in files:
        app = f.name.split("__")[0]
        rep = json.loads(f.read_text())
        rid = f"{app}-hybrid"
        if rid in ids:
            raise SystemExit(f"duplicate report id {rid}")
        ids.add(rid)
        rep["id"] = rid
        rep["target"] = f"app/benchmark/apps/{app}"  # repo-relative, no local absolute paths
        rep["stats"]["source_run"] = f"{run}/{config}"
        out = rep_dir / f"{rid}.json"
        out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
        verdicts = rep["verdicts"]
        entries.append({
            "id": rid, "file": out.name, "target": rep["target"], "created_at": rep["created_at"],
            "mode": rep["mode"], "policies": rep["policies"],
            "risk_level": (rep.get("risk") or {}).get("level", "unknown"),
            "overall_score": rep["overall_score"], "requirements": len(rep["requirements"]),
            "needs_review": sum(v["status"] == "needs_review" for v in verdicts),
        })
    for name in HAND_MADE:
        (rep_dir / name).unlink(missing_ok=True)
    index = rep_dir / "index.json"
    index.write_text(json.dumps({"generated_at": now(), "reports": entries}, indent=1) + "\n")
    return index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v1_improved")
    ap.add_argument("--config", default="hybrid-sonnet")
    ap.add_argument("--skip-reports", action="store_true")
    a = ap.parse_args()
    print("wrote", export_policies())
    if not a.skip_reports:
        print("wrote", export_reports(a.run, a.config))


if __name__ == "__main__":
    main()
