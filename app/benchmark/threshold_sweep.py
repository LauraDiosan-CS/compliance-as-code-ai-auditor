"""Hybrid routing threshold: offline sweep + leave-one-app-out (LOAO) selection.

Needs two configurations of the same results file (same code version):
  * ``deterministic``       rule verdict + graded confidence for every item
  * ``hybrid-<model>-all``  hybrid run where EVERY applicable item was sent to the LLM judge
                            (verdict = combine(rules, LLM) after Verifier / borderline gate)
For a threshold t the hybrid verdict of an item is exactly the rule verdict if the rules are
conclusive (compliant / non_compliant) with confidence >= t, else the combined verdict. So every
threshold can be simulated without new LLM calls.

LOAO: for each app, t is chosen on the other four apps (max accuracy, ties -> lower LLM share) and
evaluated on the held-out app. The pooled held-out accuracy is an honest estimate of the tuned
router; the threshold finally used is the median of the five LOAO choices.

    .venv/bin/python app/benchmark/threshold_sweep.py --run v1_improved --model sonnet
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
GAP = {"partial", "non_compliant"}
GRID = [round(0.5 + 0.025 * i, 3) for i in range(21)] + [1.01]


def simulate(det: dict, hyb: dict, t: float) -> tuple[str, bool]:
    """(prediction, routed_to_llm) for one item."""
    if hyb["pred"] == "not_applicable":
        return "not_applicable", False
    conclusive = det["pred"] in ("compliant", "non_compliant")
    if conclusive and det["confidence"] >= t:
        return det["pred"], False
    return hyb["pred"], True


def score(pairs: list[tuple[str, str, bool]]) -> dict:
    appl = [(t, p, r) for t, p, r in pairs if t != "not_applicable"]
    n = len(appl) or 1
    gaps = [p for t, p, _ in appl if t in GAP]
    f1s = []
    for lab in ("compliant", "partial", "non_compliant"):
        tp = sum(t == lab and p == lab for t, p, _ in appl)
        fp = sum(t != lab and p == lab for t, p, _ in appl)
        fn = sum(t == lab and p != lab for t, p, _ in appl)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return {
        "accuracy": sum(t == p for t, p, _ in appl) / n,
        "macro_f1": sum(f1s) / 3,
        "false_compliance": sum(p == "compliant" for p in gaps) / len(gaps) if gaps else 0.0,
        "needs_review": sum(p == "needs_review" for _, p, _ in appl) / n,
        "llm_share": sum(r for _, _, r in appl) / n,
        "n": len(appl),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v1_improved")
    ap.add_argument("--model", default="sonnet")
    args = ap.parse_args()
    data = json.loads((RESULTS / f"{args.run}.json").read_text())
    det_items = {(i["app"], i["requirement_id"]): i for i in data["configs"]["deterministic"]["items"]}
    hyb_items = {(i["app"], i["requirement_id"]): i for i in data["configs"][f"hybrid-{args.model}-all"]["items"]}
    apps = sorted({k[0] for k in hyb_items})

    def pairs_for(app_set: set[str], t: float) -> list[tuple[str, str, bool]]:
        out = []
        for k, h in hyb_items.items():
            if k[0] in app_set:
                p, r = simulate(det_items[k], h, t)
                out.append((h["truth"], p, r))
        return out

    sweep = [{"threshold": t, **score(pairs_for(set(apps), t))} for t in GRID]
    loao = []
    held_pairs: list[tuple[str, str, bool]] = []
    for app in apps:
        train = set(apps) - {app}
        best = max(GRID, key=lambda t: (round(score(pairs_for(train, t))["accuracy"], 6),
                                         -score(pairs_for(train, t))["llm_share"]))
        test = pairs_for({app}, best)
        held_pairs += test
        loao.append({"held_out": app, "chosen_threshold": best, **score(test)})
    chosen = statistics.median(r["chosen_threshold"] for r in loao)
    pooled = score(held_pairs)
    out = {"run": args.run, "model": args.model, "grid": GRID, "sweep": sweep, "loao": loao,
           "loao_pooled": pooled, "chosen_threshold": chosen,
           "note": "threshold chosen as the median of the leave-one-app-out choices"}
    (RESULTS / "threshold_sweep.json").write_text(json.dumps(out, indent=1))
    print("t      acc    mF1   falseC  NR    llm_share")
    for r in sweep:
        print(f"{r['threshold']:<6} {r['accuracy']:.3f}  {r['macro_f1']:.3f}  {r['false_compliance']:.3f}  "
              f"{r['needs_review']:.3f} {r['llm_share']:.2f}")
    for r in loao:
        print(f"LOAO held-out {r['held_out']:<22} t={r['chosen_threshold']:<6} acc={r['accuracy']:.3f}")
    print(f"LOAO pooled held-out accuracy {pooled['accuracy']:.3f}, macro-F1 {pooled['macro_f1']:.3f}, "
          f"LLM share {pooled['llm_share']:.2f};  chosen threshold (median) = {chosen}")


if __name__ == "__main__":
    main()
