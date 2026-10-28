"""Benchmark evaluation: run the auditor on every benchmark app and compare verdicts with ground truth.

Usage (from the repo root):

    .venv/bin/python app/benchmark/evaluate.py --out v0_baseline \
        --modes deterministic,hybrid,llm --model sonnet
    .venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --model haiku --append
    .venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --no-verifier --append
    .venv/bin/python app/benchmark/evaluate.py --summary-only        # rebuild results/SUMMARY.md

Outputs
    results/<out>.json                    metrics per configuration + per-item predictions
    results/<out>/reports/<app>__<cfg>.json  full AuditReport of every run (input of the web export)
    results/<out>/confusion_<cfg>.csv     5x5 confusion matrix (rows = truth, cols = prediction)
    results/SUMMARY.md                    one table over every results/*.json

Metric definitions (see README "Evaluation" section)
    applicable items      ground truth != not_applicable (165 labels)
    accuracy              exact status match on applicable items; needs_review / not_applicable count as wrong
    macro-F1              over {compliant, partial, non_compliant} on applicable items
    gap detection         binary; truth positive = partial|non_compliant; predicted positive =
                          partial|non_compliant|needs_review (anything flagged for attention)
    false-compliance rate P(pred = compliant | truth in {partial, non_compliant})  (the critical auditor failure)
    needs_review rate     share of applicable items deferred to a human
    accuracy@deferral     accuracy on applicable items that were NOT deferred
    applicability acc.    (pred == N/A) == (truth == N/A) over all 225 labels
    citation validity     share of cited evidence ids that exist in the evidence index;
                          share of compliant verdicts with >= 1 citation
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
APPS_DIR = HERE / "apps"
GT_DIR = HERE / "ground_truth"
RESULTS = HERE / "results"
POLICIES = ["eu-ai-act", "gdpr", "acme-rai"]
ALL_APPS = sorted(p.name for p in APPS_DIR.iterdir() if p.is_dir())
STATUSES = ["compliant", "partial", "non_compliant", "needs_review", "not_applicable"]
GRADED = ["compliant", "partial", "non_compliant"]
GAP = {"partial", "non_compliant"}


# ------------------------------------------------------------------ running


def config_name(mode: str, model: str | None, no_verifier: bool = False, verify_llm: bool = False,
                threshold: float | None = None) -> str:
    name = mode if mode == "deterministic" else f"{mode}-{model}"
    if mode == "hybrid" and threshold is not None:
        name += "-all" if threshold > 1 else f"-t{threshold:.2f}"
    if no_verifier:
        name += "-noverifier"
    if verify_llm:
        name += "-llmverify"
    return name


def _run_one(app: str, mode: str, model: str | None, use_cache: bool, concurrency: int,
             no_verifier: bool, verify_llm: bool, threshold: float | None = None) -> dict:
    """Run one audit in a worker process; returns the report as a JSON-able dict."""
    from ccauditor.llm.backend import ClaudeCodeBackend
    from ccauditor.pipeline import run_audit

    backend = None
    if mode != "deterministic":
        backend = ClaudeCodeBackend(model=model or "sonnet", concurrency=concurrency, use_cache=use_cache)
    t0 = time.perf_counter()
    rep = run_audit(str(APPS_DIR / app), POLICIES, mode=mode, backend=backend, model=model if backend else None,
                    verify_with_llm=verify_llm, use_verifier=not no_verifier, hybrid_threshold=threshold)
    out = json.loads(rep.model_dump_json())
    out["stats"]["wall_s"] = round(time.perf_counter() - t0, 3)
    out["target"] = f"app/benchmark/apps/{app}"  # repo-relative (no local absolute paths in results)
    return out


def load_gt(app: str) -> dict:
    return json.loads((GT_DIR / f"{app}.json").read_text())


# ------------------------------------------------------------------ metrics


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def macro_f1(pairs: list[tuple[str, str]], labels: list[str] = GRADED) -> tuple[float, dict]:
    per: dict[str, dict] = {}
    for lab in labels:
        tp = sum(t == lab and p == lab for t, p in pairs)
        fp = sum(t != lab and p == lab for t, p in pairs)
        fn = sum(t == lab and p != lab for t, p in pairs)
        pr, rc, f = _prf(tp, fp, fn)
        per[lab] = {"precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f, 4), "support": tp + fn}
    return sum(v["f1"] for v in per.values()) / len(labels), per


def compute_metrics(items: list[dict], reports: dict[str, dict], gts: dict[str, dict], concurrency: int = 3) -> dict:
    """items: one dict per (app, requirement) with truth/pred; reports: app -> report dict."""
    appl = [i for i in items if i["truth"] != "not_applicable"]
    pairs = [(i["truth"], i["pred"]) for i in appl]
    n = len(appl)
    correct = sum(t == p for t, p in pairs)
    mf1, per_class = macro_f1(pairs)

    # gap detection (binary)
    tp = sum(t in GAP and p in GAP | {"needs_review"} for t, p in pairs)
    fp = sum(t not in GAP and p in GAP | {"needs_review"} for t, p in pairs)
    fn = sum(t in GAP and p not in GAP | {"needs_review"} for t, p in pairs)
    gp, gr, gf = _prf(tp, fp, fn)
    # strict variant: needs_review does not count as a detected gap
    tps = sum(t in GAP and p in GAP for t, p in pairs)
    fps = sum(t not in GAP and p in GAP for t, p in pairs)
    fns = sum(t in GAP and p not in GAP for t, p in pairs)
    sp, sr, sf = _prf(tps, fps, fns)

    gaps_truth = [p for t, p in pairs if t in GAP]
    false_compliance = sum(p == "compliant" for p in gaps_truth) / len(gaps_truth) if gaps_truth else 0.0
    compl_truth = [p for t, p in pairs if t == "compliant"]
    false_gap = sum(p in GAP for p in compl_truth) / len(compl_truth) if compl_truth else 0.0

    deferred = [i for i in appl if i["pred"] == "needs_review"]
    kept = [i for i in appl if i["pred"] != "needs_review"]
    acc_kept = sum(i["truth"] == i["pred"] for i in kept) / len(kept) if kept else 0.0

    appl_acc = sum((i["pred"] == "not_applicable") == (i["truth"] == "not_applicable") for i in items) / len(items)

    by_cat: dict[str, list[bool]] = defaultdict(list)
    by_pol: dict[str, list[bool]] = defaultdict(list)
    by_app: dict[str, list[bool]] = defaultdict(list)
    by_method: dict[str, list[bool]] = defaultdict(list)
    for i in appl:
        ok = i["truth"] == i["pred"]
        by_cat[i["category"]].append(ok)
        by_pol[i["policy"]].append(ok)
        by_app[i["app"]].append(ok)
        by_method[i["method"]].append(ok)

    def acc(d: dict[str, list[bool]]) -> dict:
        return {k: {"accuracy": round(sum(v) / len(v), 4), "n": len(v)} for k, v in sorted(d.items())}

    conf = {t: {p: 0 for p in STATUSES} for t in STATUSES}
    for i in items:
        conf[i["truth"]][i["pred"]] += 1

    # risk classification, citations, cost
    risk_ok, cited, cited_valid, comp, comp_cited = 0, 0, 0, 0, 0
    stats_sum: Counter = Counter()
    for app, rep in reports.items():
        risk_ok += (rep.get("risk") or {}).get("level") == gts[app]["risk_level"]
        valid_ids = {e["id"] for e in rep["evidence"]}
        for v in rep["verdicts"]:
            cited += len(v["evidence_ids"])
            cited_valid += sum(e in valid_ids for e in v["evidence_ids"])
            if v["status"] == "compliant":
                comp += 1
                comp_cited += bool([e for e in v["evidence_ids"] if e in valid_ids])
        s = rep["stats"]
        for k in ("llm_calls", "llm_cache_hits", "llm_failures", "input_tokens", "output_tokens", "cost_usd",
                  "llm_latency_s", "llm_cached_cost_usd", "llm_cached_latency_s", "llm_cached_input_tokens",
                  "llm_cached_output_tokens", "n_llm_judged", "wall_s"):
            stats_sum[k] += s.get(k, 0) or 0
        stats_sum["total_s"] += s.get("timings", {}).get("total_s", 0)
    n_apps = len(reports) or 1
    calls_equiv = stats_sum["llm_calls"] + stats_sum["llm_cache_hits"]
    return {
        "n_items": len(items),
        "n_applicable": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "macro_f1": round(mf1, 4),
        "per_class": per_class,
        "gap_detection": {"precision": round(gp, 4), "recall": round(gr, 4), "f1": round(gf, 4),
                          "tp": tp, "fp": fp, "fn": fn},
        "gap_detection_strict": {"precision": round(sp, 4), "recall": round(sr, 4), "f1": round(sf, 4)},
        "false_compliance_rate": round(false_compliance, 4),
        "false_gap_rate": round(false_gap, 4),
        "needs_review_rate": round(len(deferred) / n, 4) if n else 0.0,
        "n_needs_review": len(deferred),
        "accuracy_after_deferral": round(acc_kept, 4),
        "applicability_accuracy": round(appl_acc, 4),
        "risk_accuracy": round(risk_ok / n_apps, 4),
        "risk_predictions": {app: (rep.get("risk") or {}).get("level") for app, rep in reports.items()},
        "citation_validity": round(cited_valid / cited, 4) if cited else 1.0,
        "compliant_with_citation": round(comp_cited / comp, 4) if comp else 1.0,
        "per_category": acc(by_cat),
        "per_policy": acc(by_pol),
        "per_app": acc(by_app),
        "per_method": acc(by_method),
        "confusion": conf,
        "cost": {
            "llm_calls_real": int(stats_sum["llm_calls"]),
            "llm_cache_hits": int(stats_sum["llm_cache_hits"]),
            "llm_calls_equiv": int(calls_equiv),
            "llm_failures": int(stats_sum["llm_failures"]),
            "n_llm_judged": int(stats_sum["n_llm_judged"]),
            # equivalent = real + what cached calls cost when they were first made
            "input_tokens_equiv": int(stats_sum["input_tokens"] + stats_sum["llm_cached_input_tokens"]),
            "output_tokens_equiv": int(stats_sum["output_tokens"] + stats_sum["llm_cached_output_tokens"]),
            "cost_usd_equiv": round(stats_sum["cost_usd"] + stats_sum["llm_cached_cost_usd"], 4),
            "cost_usd_real": round(stats_sum["cost_usd"], 4),
            "llm_latency_s_equiv": round(stats_sum["llm_latency_s"] + stats_sum["llm_cached_latency_s"], 2),
            "wall_s_total": round(stats_sum["wall_s"], 2),
            "wall_s_per_app": round(stats_sum["wall_s"] / n_apps, 2),
            # cold-run estimate: cached calls would have run `concurrency` at a time
            "est_wall_s_per_app": round((stats_sum["wall_s"] + stats_sum["llm_cached_latency_s"] / max(1, concurrency))
                                        / n_apps, 2),
        },
    }


def items_for(app: str, rep: dict, gt: dict) -> list[dict]:
    req_by_id = {r["id"]: r for r in rep["requirements"]}
    v_by_id = {v["requirement_id"]: v for v in rep["verdicts"]}
    out = []
    for rid, truth in gt["labels"].items():
        v = v_by_id.get(rid)
        r = req_by_id.get(rid, {})
        out.append({
            "app": app, "requirement_id": rid, "policy": r.get("policy_id", rid.split("-")[0]),
            "category": r.get("category", "other"), "severity": r.get("severity"), "truth": truth,
            "pred": v["status"] if v else "needs_review", "confidence": v["confidence"] if v else 0.0,
            "method": v["method"] if v else "missing", "n_citations": len(v["evidence_ids"]) if v else 0,
            "rationale": (v["rationale"][:600] if v else ""),
        })
    return out


# ------------------------------------------------------------------ summary


def _fmt(x: float, pct: bool = True) -> str:
    return f"{100 * x:.1f}" if pct else f"{x:.2f}"


def write_summary() -> Path:
    rows = []
    for f in sorted(RESULTS.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except ValueError:
            continue
        for cfg, m in data.get("configs", {}).items():
            rows.append((f.stem, cfg, m["metrics"]))
    lines = [
        "# Benchmark results summary",
        "",
        "Generated by `app/benchmark/evaluate.py` from `results/*.json`. 5 apps x 45 requirements "
        "(165 applicable labels). Percentages; cost = equivalent USD reported by the Claude Code CLI "
        "(`total_cost_usd`, includes calls served from the local cache at their original cost); "
        "est. s/app = wall-clock per app audit, with calls served from the cache counted at their original latency "
        "divided by the per-app concurrency (3); llm_s = summed latency of all LLM calls.",
        "",
        "| run | config | acc | macro-F1 | gap P | gap R | gap F1 | false-compl. | needs_review | acc@deferral "
        "| applic. acc | risk acc | cit. valid | compl. cited | LLM calls | cost $ | llm_s (sum) | est. s/app |",
        "|---|---|" + "---:|" * 16,
    ]
    for run, cfg, m in rows:
        g, c = m["gap_detection"], m["cost"]
        lines.append(
            f"| {run} | {cfg} | {_fmt(m['accuracy'])} | {_fmt(m['macro_f1'])} | {_fmt(g['precision'])} | "
            f"{_fmt(g['recall'])} | {_fmt(g['f1'])} | {_fmt(m['false_compliance_rate'])} | "
            f"{_fmt(m['needs_review_rate'])} | {_fmt(m['accuracy_after_deferral'])} | "
            f"{_fmt(m['applicability_accuracy'])} | {_fmt(m['risk_accuracy'])} | {_fmt(m['citation_validity'])} | "
            f"{_fmt(m['compliant_with_citation'])} | {c['llm_calls_equiv']} | {c['cost_usd_equiv']:.2f} | "
            f"{c['llm_latency_s_equiv']:.0f} | {c.get('est_wall_s_per_app', c['wall_s_per_app']):.1f} |")
    lines += ["", "## Per-category accuracy (applicable labels)", ""]
    cats = sorted({k for _, _, m in rows for k in m["per_category"]})
    lines.append("| run | config | " + " | ".join(cats) + " |")
    lines.append("|---|---|" + "---:|" * len(cats))
    for run, cfg, m in rows:
        lines.append(f"| {run} | {cfg} | " + " | ".join(
            _fmt(m["per_category"][k]["accuracy"]) if k in m["per_category"] else "-" for k in cats) + " |")
    lines += ["", "## Risk classification per app", ""]
    apps = sorted({a for _, _, m in rows for a in m["risk_predictions"]})
    lines.append("| run | config | " + " | ".join(apps) + " |")
    lines.append("|---|---|" + "---|" * len(apps))
    truth = {a: load_gt(a)["risk_level"] for a in apps}
    lines.append("| truth | | " + " | ".join(truth[a] for a in apps) + " |")
    for run, cfg, m in rows:
        lines.append(f"| {run} | {cfg} | " + " | ".join(str(m["risk_predictions"].get(a, "-")) for a in apps) + " |")
    out = RESULTS / "SUMMARY.md"
    out.write_text("\n".join(lines) + "\n")
    return out


# ------------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modes", default="deterministic,hybrid,llm")
    ap.add_argument("--apps", default=",".join(ALL_APPS))
    ap.add_argument("--model", default="sonnet", help="comma-separated model aliases for llm/hybrid modes")
    ap.add_argument("--no-cache", action="store_true", help="bypass the LLM disk cache")
    ap.add_argument("--no-verifier", action="store_true", help="ablation: disable the Verifier agent")
    ap.add_argument("--verify-llm", action="store_true", help="enable the LLM claim-support Verifier pass")
    ap.add_argument("--hybrid-threshold", type=float, default=None,
                    help="routing threshold on rule confidence (>1 = send every applicable item to the LLM); "
                         "default: pipeline.HYBRID_CONFIDENCE_THRESHOLD")
    ap.add_argument("--out", default=None, help="run name, e.g. v0_baseline (results/<out>.json)")
    ap.add_argument("--append", action="store_true", help="merge configs into an existing results/<out>.json")
    ap.add_argument("--workers", type=int, default=5, help="apps audited in parallel (processes)")
    ap.add_argument("--concurrency", type=int, default=3, help="concurrent LLM calls per app audit")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)

    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.summary_only:
        print(write_summary())
        return 0
    run = args.out or datetime.now().strftime("run_%Y%m%d_%H%M%S")
    apps = [a for a in args.apps.split(",") if a]
    modes = [m for m in args.modes.split(",") if m]
    models = [m for m in args.model.split(",") if m]
    out_json = RESULTS / f"{run}.json"
    data: dict[str, Any] = {"run": run, "configs": {}}
    if args.append and out_json.exists():
        data = json.loads(out_json.read_text())
    gts = {a: load_gt(a) for a in apps}
    rep_dir = RESULTS / run / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    jobs = []
    for mode in modes:
        for model in ([None] if mode == "deterministic" else models):
            jobs.append((mode, model, config_name(mode, model, args.no_verifier, args.verify_llm,
                                                  args.hybrid_threshold)))

    for mode, model, cfg in jobs:
        print(f"[{run}] {cfg}: auditing {len(apps)} app(s) ...", flush=True)
        t0 = time.perf_counter()
        reports: dict[str, dict] = {}
        with ProcessPoolExecutor(max_workers=max(1, min(args.workers, len(apps)))) as ex:
            futs = {a: ex.submit(_run_one, a, mode, model, not args.no_cache, args.concurrency,
                                 args.no_verifier, args.verify_llm,
                                 args.hybrid_threshold if mode == "hybrid" else None) for a in apps}
            for a, f in futs.items():
                reports[a] = f.result()
                s = reports[a]["stats"]
                print(f"   {a}: score {reports[a]['overall_score']}, risk {reports[a]['risk']['level']}, "
                      f"llm calls {s.get('llm_calls')} (+{s.get('llm_cache_hits')} cached), "
                      f"{s.get('wall_s')}s", flush=True)
        items = [it for a in apps for it in items_for(a, reports[a], gts[a])]
        metrics = compute_metrics(items, reports, gts, args.concurrency)
        for a, rep in reports.items():
            (rep_dir / f"{a}__{cfg}.json").write_text(json.dumps(rep, indent=1))
        conf = metrics["confusion"]
        csv = ["truth\\pred," + ",".join(STATUSES)] + [f"{t}," + ",".join(str(conf[t][p]) for p in STATUSES)
                                                       for t in STATUSES]
        (RESULTS / run / f"confusion_{cfg}.csv").write_text("\n".join(csv) + "\n")
        data["configs"][cfg] = {
            "mode": mode, "model": model, "apps": apps, "no_verifier": args.no_verifier,
            "verify_llm": args.verify_llm, "use_cache": not args.no_cache,
            "hybrid_threshold": reports[apps[0]]["stats"].get("hybrid_threshold"),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "metrics": metrics, "items": items,
        }
        out_json.write_text(json.dumps(data, indent=1))
        m = metrics
        print(f"   => acc {m['accuracy']:.3f}  macroF1 {m['macro_f1']:.3f}  gapR {m['gap_detection']['recall']:.3f}  "
              f"falseCompl {m['false_compliance_rate']:.3f}  NR {m['needs_review_rate']:.3f}  "
              f"risk {m['risk_accuracy']:.2f}  cost ${m['cost']['cost_usd_equiv']:.2f}", flush=True)
    print(write_summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
