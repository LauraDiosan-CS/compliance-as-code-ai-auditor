"""Figures of the v0 baseline results (Seminar 4 report: pipeline and first results).

Usage (from the repo root):
    .venv/bin/python app/benchmark/stats_tests.py --run v0_baseline   # -> results/stats_tests_v0.json (CIs)
    .venv/bin/python app/benchmark/plot_v0.py

Reads results/v0_baseline.json (+ results/stats_tests_v0.json for the error bars) and writes, in the shared
report style (app/notebooks/plotstyle.py), to docs/report/figures/:
    results_v0_modes.{pdf,png}         accuracy, macro-F1, gap recall, false-compliance rate per configuration
    results_v0_confusion.{pdf,png}     confusion matrices of the three configurations (all 225 labels)
    results_v0_per_category.{pdf,png}  accuracy per requirement category
    results_v0_cost.{pdf,png}          LLM calls, equivalent cost and time per app audit
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "notebooks"))
import plotstyle as ps  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = HERE / "results"
CONFIGS = [("deterministic", "rules only", "deterministic"),
           ("llm-sonnet", "LLM only (Sonnet)", "llm"),
           ("hybrid-sonnet", "hybrid (Sonnet)", "hybrid")]
SHORT = {"compliant": "C", "partial": "P", "non_compliant": "NC", "needs_review": "NR", "not_applicable": "N/A"}


def main() -> None:
    data = json.loads((RESULTS / "v0_baseline.json").read_text())["configs"]
    stats_p = RESULTS / "stats_tests_v0.json"
    boot = json.loads(stats_p.read_text())["bootstrap"] if stats_p.exists() else {}

    # ---------------------------------------------------------------- 1. headline metrics
    metrics = [("accuracy", "Accuracy", "accuracy"), ("macro_f1", "Macro-F1", "macro_f1"),
               ("gap_recall", "Gap recall", None), ("false_compliance_rate", "False-compliance\nrate (lower = better)",
                                                    "false_compliance")]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(len(metrics))
    w = 0.26
    for j, (cfg, label, mode) in enumerate(CONFIGS):
        m = data[cfg]["metrics"]
        vals, lo, hi = [], [], []
        for key, _, bkey in metrics:
            v = m["gap_detection"]["recall"] if key == "gap_recall" else m[key]
            vals.append(100 * v)
            if bkey and f"v0_baseline/{cfg}" in boot:
                ci = boot[f"v0_baseline/{cfg}"][bkey]["ci95"]
                lo.append(100 * (v - ci[0]))
                hi.append(100 * (ci[1] - v))
            else:
                lo.append(0)
                hi.append(0)
        bars = ax.bar(x + (j - 1) * w, vals, w, label=label, color=ps.MODE_COLOR[mode])
        ax.errorbar(x + (j - 1) * w, vals, yerr=[lo, hi], fmt="none", ecolor=ps.INK2, elinewidth=0.8, capsize=2)
        for b in bars:  # value at the foot of the bar, clear of the error bars
            h = b.get_height()
            ax.annotate(f"{h:.1f}", (b.get_x() + b.get_width() / 2, 2.5 if h > 8 else h + 1.5), ha="center",
                        va="bottom", fontsize=7, color="white" if h > 8 else ps.INK)
    ax.set_xticks(x, [m[1] for m in metrics])
    ax.set_ylabel("%")
    ax.set_ylim(0, 112)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.13))
    ps.save(fig, "results_v0_modes")
    plt.close(fig)

    # ---------------------------------------------------------------- 2. confusion matrices
    order = ps.STATUS_ORDER
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.1), constrained_layout=True)
    for ax, (cfg, label, _) in zip(axes, CONFIGS):
        conf = data[cfg]["metrics"]["confusion"]
        mat = np.array([[conf.get(t, {}).get(p, 0) for p in order] for t in order if t != "needs_review"])
        rows = [t for t in order if t != "needs_review"]
        ax.imshow(mat, cmap="Blues", vmin=0, vmax=max(60, mat.max()))
        for i in range(mat.shape[0]):
            for k in range(mat.shape[1]):
                v = mat[i, k]
                if v:
                    ax.text(k, i, str(v), ha="center", va="center", fontsize=8,
                            color="white" if v > 40 else ps.INK,
                            fontweight="bold" if rows[i] == order[k] else "normal")
        ax.set_xticks(range(len(order)), [SHORT[o] for o in order])
        ax.set_yticks(range(len(rows)), [SHORT[o] for o in rows])
        ax.set_xlabel("predicted")
        ax.set_title(label)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_ylabel("ground truth")
    ps.save(fig, "results_v0_confusion")
    plt.close(fig)

    # ---------------------------------------------------------------- 3. per-category accuracy
    cats = sorted(data["deterministic"]["metrics"]["per_category"])
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    x = np.arange(len(cats))
    for j, (cfg, label, mode) in enumerate(CONFIGS):
        pc = data[cfg]["metrics"]["per_category"]
        vals = [100 * (pc[c]["accuracy"] if isinstance(pc[c], dict) else pc[c]) for c in cats]
        ax.bar(x + (j - 1) * w, vals, w, label=label, color=ps.MODE_COLOR[mode])
    ns = [data["deterministic"]["metrics"]["per_category"][c].get("n", "") if isinstance(
        data["deterministic"]["metrics"]["per_category"][c], dict) else "" for c in cats]
    ax.set_xticks(x, [f"{c.replace('_', ' ')}\n(n={n})" for c, n in zip(cats, ns)], rotation=35, ha="right",
                  fontsize=7.5)
    ax.set_ylabel("accuracy (%)")
    ax.set_ylim(0, 110)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.14))
    ps.save(fig, "results_v0_per_category")
    plt.close(fig)

    # ---------------------------------------------------------------- 4. cost and latency
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.4), constrained_layout=True)
    panels = [("llm_calls_equiv", "LLM calls (5 audits)", "{:.0f}"),
              ("cost_usd_equiv", "equivalent cost (USD, 5 audits)", "{:.2f}"),
              ("wall_s_per_app", "seconds per app audit", "{:.1f}")]
    for ax, (key, title, fmt) in zip(axes, panels):
        vals = [data[cfg]["metrics"]["cost"][key] for cfg, _, _ in CONFIGS]
        bars = ax.bar(range(3), vals, 0.6, color=[ps.MODE_COLOR[m] for _, _, m in CONFIGS])
        ps.bar_labels(ax, bars, fmt=fmt, fontsize=7.5, show_zero=True)
        ax.set_xticks(range(3), ["rules", "LLM", "hybrid"])
        ax.set_title(title, fontsize=8.5)
        ax.set_ylim(0, max(vals) * 1.2 if max(vals) else 1)
    ps.save(fig, "results_v0_cost")
    plt.close(fig)
    print("wrote results_v0_{modes,confusion,per_category,cost}.{pdf,png} to", ps.FIG_DIR)


if __name__ == "__main__":
    main()
