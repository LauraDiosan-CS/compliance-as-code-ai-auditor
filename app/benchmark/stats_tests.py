"""Statistical validation of benchmark results: bootstrap CIs and exact McNemar tests.

Usage (from the repo root):
    .venv/bin/python app/benchmark/stats_tests.py            # prints a table and writes results/stats_tests.json

* 95% percentile bootstrap CIs (10,000 resamples of the 165 applicable items, seed 0) for accuracy,
  macro-F1 over {compliant, partial, non_compliant} and false-compliance rate.
* Exact two-sided McNemar test on paired per-item correctness between configurations.
Definitions follow evaluate.py (needs_review / wrong N/A count as errors).
"""

from __future__ import annotations

import json
import random
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
GRADED = ["compliant", "partial", "non_compliant"]
GAP = {"partial", "non_compliant"}
B = 10_000

CONFIGS = [
    ("v0_baseline", "deterministic"), ("v0_baseline", "hybrid-sonnet"), ("v0_baseline", "llm-sonnet"),
    ("v1_improved", "deterministic"), ("v1_improved", "hybrid-sonnet"), ("v1_improved", "hybrid-sonnet-all"),
    ("v1_improved", "llm-sonnet"), ("v1_improved", "hybrid-haiku"), ("v1_improved", "llm-haiku"),
    ("v1_improved", "hybrid-sonnet-llmverify"),
]
PAIRS = [
    (("v1_improved", "hybrid-sonnet"), ("v1_improved", "deterministic")),
    (("v1_improved", "hybrid-sonnet"), ("v1_improved", "llm-sonnet")),
    (("v1_improved", "hybrid-sonnet"), ("v1_improved", "hybrid-sonnet-all")),
    (("v1_improved", "hybrid-sonnet"), ("v1_improved", "hybrid-haiku")),
    (("v1_improved", "hybrid-sonnet"), ("v1_improved", "hybrid-sonnet-llmverify")),
    (("v1_improved", "llm-sonnet"), ("v0_baseline", "llm-sonnet")),
    (("v1_improved", "hybrid-sonnet"), ("v0_baseline", "hybrid-sonnet")),
    (("v1_improved", "deterministic"), ("v0_baseline", "deterministic")),
]


def load(run: str, cfg: str) -> dict[tuple[str, str], tuple[str, str]]:
    data = json.loads((RESULTS / f"{run}.json").read_text())
    items = data["configs"][cfg]["items"]
    return {(i["app"], i["requirement_id"]): (i["truth"], i["pred"]) for i in items if i["truth"] != "not_applicable"}


def accuracy(pairs):
    return sum(t == p for t, p in pairs) / len(pairs)


def macro_f1(pairs):
    f1s = []
    for c in GRADED:
        tp = sum(t == c and p == c for t, p in pairs)
        fp = sum(t != c and p == c for t, p in pairs)
        fn = sum(t == c and p != c for t, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return sum(f1s) / len(f1s)


def fcr(pairs):
    gaps = [(t, p) for t, p in pairs if t in GAP]
    return sum(p == "compliant" for _, p in gaps) / len(gaps) if gaps else 0.0


def bootstrap(pairs, fn, rng):
    n = len(pairs)
    vals = sorted(fn([pairs[rng.randrange(n)] for _ in range(n)]) for _ in range(B))
    return vals[int(0.025 * B)], vals[int(0.975 * B) - 1]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def main() -> None:
    out: dict = {"bootstrap": {}, "mcnemar": []}
    print(f"{'config':40s} {'acc [95% CI]':24s} {'macro-F1 [95% CI]':24s} {'FCR [95% CI]':22s}")
    for run, cfg in CONFIGS:
        d = load(run, cfg)
        pairs = [d[k] for k in sorted(d)]
        rng = random.Random(0)
        row = {}
        for name, fn in (("accuracy", accuracy), ("macro_f1", macro_f1), ("false_compliance", fcr)):
            lo, hi = bootstrap(pairs, fn, rng)
            row[name] = {"value": round(fn(pairs), 4), "ci95": [round(lo, 4), round(hi, 4)]}
        out["bootstrap"][f"{run}/{cfg}"] = row
        fmt = lambda r: f"{100*r['value']:5.1f} [{100*r['ci95'][0]:4.1f}, {100*r['ci95'][1]:4.1f}]"
        print(f"{run + '/' + cfg:40s} {fmt(row['accuracy']):24s} {fmt(row['macro_f1']):24s} {fmt(row['false_compliance']):22s}")
    print()
    for a, b in PAIRS:
        da, db = load(*a), load(*b)
        keys = sorted(set(da) & set(db))
        only_a = sum(da[k][0] == da[k][1] and db[k][0] != db[k][1] for k in keys)
        only_b = sum(da[k][0] != da[k][1] and db[k][0] == db[k][1] for k in keys)
        p = mcnemar_exact(only_a, only_b)
        out["mcnemar"].append({"a": "/".join(a), "b": "/".join(b), "a_right_b_wrong": only_a,
                               "a_wrong_b_right": only_b, "p_value": round(p, 5)})
        print(f"McNemar {'/'.join(a):32s} vs {'/'.join(b):36s} a>b {only_a:3d}  b>a {only_b:3d}  p={p:.4g}")
    (RESULTS / "stats_tests.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
