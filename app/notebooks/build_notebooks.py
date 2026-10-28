"""Build (and optionally execute) the analysis notebooks from source cells kept here.

    .venv/bin/python app/notebooks/build_notebooks.py --execute

Keeping the cells in a .py file makes notebook diffs reviewable; the executed .ipynb files (with outputs)
are committed next to this script.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent

SETUP = r'''
import sys, json, re
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path.cwd()
ROOT = HERE.parents[1] if HERE.name == "notebooks" else Path("/Users/edi/Desktop/aml-project")
sys.path.insert(0, str(ROOT / "app" / "notebooks"))
import plotstyle as ps
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)
'''

EDA = [
    ("md", """# 01 - Exploratory data analysis

Compliance-as-Code AI Auditor (AML 2026-2027, topic #5). This notebook describes the two inputs of the
auditor: the **policy corpus** (regulation / policy text split into citable clauses, plus the curated,
machine-checkable requirements derived from them) and the **benchmark** (five hand-labelled AI application
repositories). Figures are written to `docs/report/figures/` (PDF + PNG)."""),
    ("code", SETUP),
    ("code", r'''
from ccauditor.policies.loader import get_policy, get_requirements
from ccauditor.evidence.collector import collect

POLICY_IDS = ["eu-ai-act", "gdpr", "acme-rai"]
policies = {p: get_policy(p) for p in POLICY_IDS}
reqs = {p: get_requirements(p) for p in POLICY_IDS}

clauses = pd.DataFrame([
    {"policy": p, "id": c.id, "parent": c.parent_id, "top_level": c.parent_id is None,
     "article": (c.parent_id or c.id).split("/", 1)[1], "chars": len(c.text), "words": len(c.text.split())}
    for p, pol in policies.items() for c in pol.clauses])
R = pd.DataFrame([
    {"policy": r.policy_id, "id": r.id, "category": r.category.value, "severity": r.severity,
     "applies_to": ",".join(sorted(a.value for a in r.applies_to)), "n_checks": len(r.checks),
     "check_types": ",".join(sorted({c.type for c in r.checks})),
     "n_clauses": len(r.clause_ids), "has_guidance": bool(r.llm_guidance), "n_queries": len(r.evidence_queries)}
    for p in POLICY_IDS for r in reqs[p]])
print(clauses.groupby("policy").agg(clauses=("id", "count"), articles=("top_level", "sum"),
                                     median_words=("words", "median"), max_words=("words", "max")))
print()
print(R.groupby("policy").agg(requirements=("id", "count"), checks=("n_checks", "sum"),
                               with_checks=("n_checks", lambda s: int((s > 0).sum())),
                               with_guidance=("has_guidance", "sum")))
'''),
    ("md", "## Policy corpus: clauses per article and clause length"),
    ("code", r'''
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.7, 1]})
per_art = clauses.groupby(["policy", "article"]).size().rename("n").reset_index()
order = []
for i, p in enumerate(POLICY_IDS):
    sub = per_art[per_art.policy == p]
    order.append(sub.assign(color=ps.CAT[i]))
per_art = pd.concat(order)
ax = axes[0]
ax.bar(range(len(per_art)), per_art.n, color=per_art.color, width=0.8)
ax.set_xticks(range(len(per_art)), per_art.article, rotation=90, fontsize=6.5)
ax.set_ylabel("clauses (article + paragraphs)")
ax.set_title("Clauses per article / section")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=ps.CAT[i], label=p) for i, p in enumerate(POLICY_IDS)], loc="upper right")
ax = axes[1]
bins = np.logspace(np.log10(max(1, clauses.words.min())), np.log10(clauses.words.max()), 18)
for i, p in enumerate(POLICY_IDS):
    ax.hist(clauses[clauses.policy == p].words, bins=bins, histtype="step", linewidth=2, color=ps.CAT[i], label=p)
ax.set_xscale("log"); ax.set_xlabel("words per clause (log)"); ax.set_ylabel("clauses")
ax.set_title("Clause length distribution"); ax.legend()
fig.tight_layout(); ps.save(fig, "eda_clauses"); plt.show()
'''),
    ("md", "## Requirements: categories, severity, applicability and deterministic coverage"),
    ("code", r'''
fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
ct = pd.crosstab(R.category, R.policy)[POLICY_IDS]
ct = ct.loc[ct.sum(axis=1).sort_values().index]
left = np.zeros(len(ct))
for i, p in enumerate(POLICY_IDS):
    axes[0].barh(ct.index, ct[p], left=left, color=ps.CAT[i], label=p, height=0.7)
    left += ct[p].values
axes[0].set_title("Requirements per category"); axes[0].set_xlabel("requirements"); axes[0].legend(loc="lower right")
axes[0].grid(axis="x"); axes[0].grid(axis="y", visible=False)

sev_order = ["critical", "high", "medium", "low"]
ct = pd.crosstab(R.severity, R.policy).reindex(sev_order).fillna(0)[POLICY_IDS]
x = np.arange(len(sev_order)); w = 0.26
for i, p in enumerate(POLICY_IDS):
    b = axes[1].bar(x + (i - 1) * w, ct[p], width=w, color=ps.CAT[i], label=p)
    ps.bar_labels(axes[1], b)
axes[1].set_xticks(x, sev_order); axes[1].set_title("Severity"); axes[1].set_ylabel("requirements")

ct = pd.crosstab(R.n_checks, R.policy).reindex(columns=POLICY_IDS).fillna(0)
x = np.arange(len(ct));
for i, p in enumerate(POLICY_IDS):
    b = axes[2].bar(x + (i - 1) * w, ct[p], width=w, color=ps.CAT[i], label=p)
    ps.bar_labels(axes[2], b)
axes[2].set_xticks(x, ct.index); axes[2].set_xlabel("deterministic checks per requirement")
axes[2].set_title("Checks per requirement (0 = LLM / human only)")
fig.tight_layout(); ps.save(fig, "eda_requirements"); plt.show()

print(pd.crosstab(R.applies_to, R.policy))
print()
allchecks = pd.DataFrame([{"policy": r.policy_id, "type": c.type, "expect": c.expect,
                           "kinds": ",".join(k.value for k in c.kinds) or "(any)"}
                          for p in POLICY_IDS for r in reqs[p] for c in r.checks])
print(pd.crosstab([allchecks.type, allchecks.expect], allchecks.policy))
cov = (R.n_checks > 0).mean()
print(f"\nDeterministic coverage: {cov:.1%} of requirements have >= 1 check; "
      f"{R.has_guidance.mean():.0%} carry LLM guidance.")
'''),
    ("md", "## Benchmark repositories: files, evidence kinds and chunks"),
    ("code", r'''
APPS = sorted(p.name for p in (ROOT / "app/benchmark/apps").iterdir() if p.is_dir())
idx = {a: collect(ROOT / "app/benchmark/apps" / a) for a in APPS}
E = pd.DataFrame([{"app": a, "path": e.path, "kind": e.kind.value, "lines": e.end_line - e.start_line + 1,
                   "chars": len(e.snippet), "signals": e.signal}
                  for a, ix in idx.items() for e in ix.items])
files = E.drop_duplicates(["app", "path"])
kinds = ["code", "config", "iac", "doc", "model_card", "log"]
fk = pd.crosstab(files.app, files.kind).reindex(columns=kinds).fillna(0).astype(int)
ck = pd.crosstab(E.app, E.kind).reindex(columns=kinds).fillna(0).astype(int)
summary = pd.DataFrame({"files": fk.sum(axis=1), "chunks": ck.sum(axis=1),
                        "chars": E.groupby("app").chars.sum()})
print(summary); print(); print(fk)

fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
for ax, tab, title in [(axes[0], fk, "Files per evidence kind"), (axes[1], ck, "Evidence chunks per kind")]:
    left = np.zeros(len(tab))
    for i, k in enumerate(kinds):
        ax.barh(tab.index, tab[k], left=left, color=ps.CAT[i], label=k, height=0.65)
        left += tab[k].values
    ax.set_title(title); ax.grid(axis="x"); ax.grid(axis="y", visible=False)
axes[1].set_yticklabels([])
axes[0].legend(ncol=3, loc="upper center", bbox_to_anchor=(1.05, -0.12))
fig.tight_layout(); ps.save(fig, "eda_benchmark_files"); plt.show()
'''),
    ("md", "### Signal frequency (regex detectors of the evidence collector)"),
    ("code", r'''
sig = E.assign(signal=E.signals.str.split(",")).explode("signal")
sig = sig[sig.signal.fillna("") != ""]
st = pd.crosstab(sig.signal, sig.app)
st = st.loc[st.sum(axis=1).sort_values(ascending=False).index]
share = st / ck.sum(axis=1)  # share of the app's chunks carrying the signal
fig, ax = plt.subplots(figsize=(7, 5.2))
im = ax.imshow(share.values, cmap="Blues", aspect="auto", vmin=0, vmax=1)
ax.set_xticks(range(len(share.columns)), share.columns, rotation=25, ha="right")
ax.set_yticks(range(len(share.index)), share.index)
for i in range(share.shape[0]):
    for j in range(share.shape[1]):
        v = share.values[i, j]
        ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7, color="white" if v > 0.55 else ps.INK)
ax.grid(False); ax.set_title("Share of evidence chunks carrying each signal")
fig.colorbar(im, ax=ax, fraction=0.04, format=lambda x, _: f"{x:.0%}")
fig.tight_layout(); ps.save(fig, "eda_signals"); plt.show()
'''),
    ("md", "## Ground-truth label distribution"),
    ("code", r'''
GT = {a: json.loads((ROOT / f"app/benchmark/ground_truth/{a}.json").read_text()) for a in APPS}
req_meta = R.set_index("id")
L = pd.DataFrame([{"app": a, "risk": g["risk_level"], "id": rid, "status": st,
                   "category": req_meta.loc[rid, "category"], "policy": req_meta.loc[rid, "policy"]}
                  for a, g in GT.items() for rid, st in g["labels"].items()])
order = [s for s in ps.STATUS_ORDER if s in set(L.status)]
fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1, 1.3]})
for ax, col, title in [(axes[0], "app", "Labels per app"), (axes[1], "category", "Applicable labels per category")]:
    data = L if col == "app" else L[L.status != "not_applicable"]
    tab = pd.crosstab(data[col], data.status).reindex(columns=order).fillna(0)
    if col == "category":
        tab = tab.loc[tab.sum(axis=1).sort_values().index]
    left = np.zeros(len(tab))
    for s in order:
        if s not in tab or tab[s].sum() == 0:
            continue
        ax.barh(tab.index, tab[s], left=left, color=ps.STATUS_COLOR[s], label=s, height=0.65)
        left += tab[s].values
    ax.set_title(title); ax.grid(axis="x"); ax.grid(axis="y", visible=False)
axes[0].set_yticks(range(len(APPS)), [f"{a}\n({GT[a]['risk_level']})" for a in APPS], fontsize=8)
axes[0].legend(ncol=4, loc="upper center", bbox_to_anchor=(1.1, -0.1))
fig.tight_layout(); ps.save(fig, "eda_labels"); plt.show()
print(pd.crosstab(L.app, L.status, margins=True))
'''),
    ("md", """## Observations

* **Corpus.** The EU AI Act excerpt dominates (108 clauses over ~20 articles/annex points); GDPR and the
  internal ACME policy are smaller (~30 clauses each). Clause length is heavy-tailed (a few long
  paragraphs, many one-sentence items), so evidence prompts quote clauses truncated to 1,500 chars.
* **Requirements.** 45 curated requirements, all with LLM guidance; 42/45 have at least one deterministic
  check (mostly regex `pattern` checks, a few `file_exists`). Three requirements (AIA-DATA-02,
  GDPR-ADM-01, ACME-11) have no check and can only be decided by the LLM judge or a human: deterministic
  mode is structurally capped below 100% recall on them. Many requirements apply only to high-risk systems,
  so the risk tier decides up to 27 of 45 labels for a minimal-risk app: **risk classification errors
  propagate to applicability**.
* **Benchmark.** Five small repositories (13-20 files) mixing code, config, IaC, docs, model cards and logs.
  Signals are not discriminative on their own (e.g. `pii_field` and `model_call` fire in every app,
  `logging_call` fires in the app whose logging is commented out), which motivates comment-aware
  matching and an LLM judge.
* **Labels.** 225 labels: 100 compliant, 14 partial, 51 non-compliant, 60 not applicable. The classes are
  imbalanced (partial is rare, 8.5% of applicable labels), so we report macro-F1 alongside accuracy and
  focus on gap recall / false-compliance rate, the errors that matter for an auditor. quickhire is almost
  entirely non-compliant while hireright/credit-lens are mostly compliant, so per-app accuracy is
  informative about failure modes (false negatives vs false positives)."""),
]

RESULTS = [
    ("md", """# 02 - Evaluation results

Loads `app/benchmark/results/*.json` (written by `app/benchmark/evaluate.py`) and compares deterministic,
LLM and hybrid modes before (v0) and after (v1) the improvements. Figures go to `docs/report/figures/`."""),
    ("code", SETUP),
    ("code", r'''
RES = ROOT / "app/benchmark/results"
runs = {f.stem: d for f in sorted(RES.glob("*.json")) if "configs" in (d := json.loads(f.read_text()))}
rows = []
for run, d in runs.items():
    for cfg, c in d["configs"].items():
        m = c["metrics"]
        rows.append({"run": run, "config": cfg, "mode": c["mode"], "model": c.get("model"),
                     "accuracy": m["accuracy"], "macro_f1": m["macro_f1"],
                     "gap_P": m["gap_detection"]["precision"], "gap_R": m["gap_detection"]["recall"],
                     "gap_F1": m["gap_detection"]["f1"], "false_compliance": m["false_compliance_rate"],
                     "needs_review": m["needs_review_rate"], "acc_after_deferral": m["accuracy_after_deferral"],
                     "applicability_acc": m["applicability_accuracy"], "risk_acc": m["risk_accuracy"],
                     "citation_valid": m["citation_validity"], "compliant_cited": m["compliant_with_citation"],
                     "llm_calls": m["cost"]["llm_calls_equiv"], "cost_usd": m["cost"]["cost_usd_equiv"],
                     "llm_s": m["cost"]["llm_latency_s_equiv"], "wall_s_app": m["cost"]["wall_s_per_app"]})
T = pd.DataFrame(rows)
T.style.format({c: "{:.3f}" for c in T.columns if T[c].dtype == float})
'''),
    ("code", r'''
T.round(3)
'''),
    ("md", "## Headline comparison (v0 baseline vs v1 improved)"),
    ("code", r'''
main = T[T.config.isin(["deterministic", "hybrid-sonnet", "llm-sonnet"])].copy()
main["label"] = main.run.str.split("_").str[0] + " " + main.config.str.replace("-sonnet", "")
metrics = [("accuracy", "Accuracy"), ("macro_f1", "Macro-F1"), ("gap_R", "Gap recall"),
           ("false_compliance", "False-compliance rate (lower is better)")]
fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharey=False)
modes = ["deterministic", "hybrid", "llm"]
x = np.arange(len(modes)); w = 0.38
for ax, (col, title) in zip(axes, metrics):
    for k, run in enumerate(sorted(main.run.unique())):
        sub = main[main.run == run].set_index("mode").reindex(modes)
        b = ax.bar(x + (k - 0.5) * w, sub[col], width=w, color=[ps.MODE_COLOR[m] for m in modes],
                   alpha=0.45 if k == 0 else 1.0, label=run)
        ps.bar_labels(ax, b, fmt="{:.2f}", fontsize=7, show_zero=True)
    ax.set_xticks(x, modes); ax.set_title(title, fontsize=9.5); ax.set_ylim(0, 1.08 if col != "false_compliance" else max(0.3, main[col].max() * 1.3))
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color="#999", alpha=0.45, label="v0 baseline (light bars)"),
                    Patch(color="#555", label="v1 improved (solid bars)")],
           loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=(0, 0.05, 1, 1)); ps.save(fig, "results_v0_v1"); plt.show()
'''),
    ("md", "## Quality vs cost"),
    ("code", r'''
fig, ax = plt.subplots(figsize=(7, 4.2))
# ablations with identical scores (no-verifier) are omitted here; see the table above
OFFSETS = {"hybrid-sonnet-llmverify": (-118, 3), "llm-sonnet": (6, 3), "hybrid-sonnet-all": (6, -10),
           "llm-haiku": (5, -9)}
for _, r in T[~T.config.str.contains("noverifier")].iterrows():
    mode = r["mode"]
    marker = "o" if r.run.startswith("v1") else "s"
    ax.scatter(max(r.cost_usd, 0.005), r.macro_f1, s=70, color=ps.MODE_COLOR[mode], marker=marker,
               edgecolor="white", linewidth=1.5, zorder=3, alpha=1 if r.run.startswith("v1") else 0.5)
    off = OFFSETS.get(r.config, (5, 2)) if r.run.startswith("v1") else (5, 2)
    ax.annotate(f"{r.run.split('_')[0]} {r.config}", (max(r.cost_usd, 0.005), r.macro_f1), fontsize=6.5,
                xytext=off, textcoords="offset points", color=ps.INK2)
ax.set_xscale("log"); ax.set_xlabel("equivalent LLM cost for the 5 apps, USD (log; deterministic at 0)")
ax.set_ylabel("macro-F1"); ax.set_title("Quality vs cost per configuration"); ax.grid(axis="both")
ax.legend(handles=[Patch(color=c, label=m) for m, c in ps.MODE_COLOR.items()], loc="upper left",
          title="squares = v0, circles = v1", title_fontsize=7)
fig.tight_layout(); ps.save(fig, "results_cost_quality"); plt.show()
'''),
    ("md", "## Confusion matrices (rows = ground truth, columns = prediction, all 225 labels)"),
    ("code", r'''
def plot_conf(ax, conf, title):
    S = ps.STATUS_ORDER
    M = np.array([[conf[t][p] for p in S] for t in S])
    ax.imshow(M, cmap="Blues", vmin=0, vmax=M.max())
    short = ["C", "P", "NC", "NR", "N/A"]
    ax.set_xticks(range(5), short); ax.set_yticks(range(5), short)
    for i in range(5):
        for j in range(5):
            if M[i, j]:
                ax.text(j, i, M[i, j], ha="center", va="center", fontsize=8,
                        color="white" if M[i, j] > M.max() * 0.55 else ps.INK)
    ax.set_title(title, fontsize=9); ax.grid(False)
    ax.set_xlabel("predicted"); ax.set_ylabel("truth")

cfgs = [(run, cfg) for run in sorted(runs) for cfg in ["deterministic", "hybrid-sonnet", "llm-sonnet"]
        if cfg in runs[run]["configs"]]
fig, axes = plt.subplots(2, 3, figsize=(10, 6.6))
for ax, (run, cfg) in zip(axes.flat, cfgs):
    plot_conf(ax, runs[run]["configs"][cfg]["metrics"]["confusion"], f"{run.split('_')[0]} {cfg}")
for ax in list(axes.flat)[len(cfgs):]:
    ax.axis("off")
fig.tight_layout(); ps.save(fig, "results_confusion"); plt.show()
'''),
    ("md", "## Per-category accuracy"),
    ("code", r'''
latest = sorted(runs)[-1]
cats = sorted({k for run in runs.values() for c in run["configs"].values() for k in c["metrics"]["per_category"]})
fig, ax = plt.subplots(figsize=(10, 3.8))
sel = [(r, c) for r in sorted(runs) for c in ["deterministic", "hybrid-sonnet", "llm-sonnet"] if c in runs[r]["configs"]]
w = 0.8 / len(sel); x = np.arange(len(cats))
for k, (r, c) in enumerate(sel):
    pc = runs[r]["configs"][c]["metrics"]["per_category"]
    vals = [pc.get(cat, {}).get("accuracy", np.nan) for cat in cats]
    mode = runs[r]["configs"][c]["mode"]
    ax.bar(x + (k - len(sel) / 2 + 0.5) * w, vals, width=w, color=ps.MODE_COLOR[mode],
           alpha=0.45 if r.startswith("v0") else 1.0, label=f"{r.split('_')[0]} {c}")
ax.set_xticks(x, [c.replace("_", "\n") for c in cats], fontsize=7.5); ax.set_ylim(0, 1.05)
ax.set_ylabel("accuracy (applicable labels)"); ax.set_title("Accuracy per requirement category")
ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.22))
fig.tight_layout(); ps.save(fig, "results_per_category"); plt.show()
n = pd.Series({cat: runs[latest]["configs"]["deterministic"]["metrics"]["per_category"][cat]["n"] for cat in cats})
print("applicable labels per category:\n", n.to_string())
'''),
    ("md", "## Hybrid routing threshold (leave-one-app-out)"),
    ("code", r'''
sweep_file = RES / "threshold_sweep.json"
if sweep_file.exists():
    sw = json.loads(sweep_file.read_text())
    S = pd.DataFrame(sw["sweep"])
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(S.threshold, S.accuracy, color=ps.CAT[1], label="accuracy (all 5 apps)")
    ax.plot(S.threshold, S.macro_f1, color=ps.CAT[0], label="macro-F1")
    ax.plot(S.threshold, S.false_compliance, color=ps.CAT[7], linestyle="--", label="false-compliance rate")
    ax2 = ax.twinx() if False else None
    ax.bar(S.threshold, S.llm_share, width=0.02, color="#c9c8c2", label="share of items sent to LLM", zorder=0)
    ax.axvline(sw["chosen_threshold"], color=ps.INK2, linestyle="--", linewidth=1)
    ax.set_xlabel("routing threshold on rule-engine confidence"); ax.set_ylim(0, 1.02)
    ax.set_title("Hybrid: rule confidence threshold sweep (dashed vertical = LOAO choice)")
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4)
    fig.tight_layout(); ps.save(fig, "results_threshold_sweep"); plt.show()
    print(pd.DataFrame(sw["loao"]).round(3))
else:
    print("no threshold_sweep.json")
'''),
    ("md", "## Error analysis: remaining hybrid errors"),
    ("code", r'''
cfg = "hybrid-sonnet"
items = pd.DataFrame(runs[latest]["configs"][cfg]["items"])
err = items[(items.truth != items.pred) & (items.truth != "not_applicable")]
print(f"{len(err)} errors on {(items.truth != 'not_applicable').sum()} applicable labels ({latest}, {cfg})")
print(pd.crosstab(err.truth, err.pred))
err[["app", "requirement_id", "truth", "pred", "confidence", "method"]].sort_values(["app", "requirement_id"])
'''),
]


def make(cells, path: Path) -> None:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [nbf.v4.new_markdown_cell(src.strip()) if kind == "md" else nbf.v4.new_code_cell(src.strip())
                for kind, src in cells]
    nbf.write(nb, path)


def execute(path: Path) -> None:
    from nbconvert.preprocessors import ExecutePreprocessor

    nb = nbf.read(path, as_version=4)
    ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(HERE)}})
    nbf.write(nb, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", choices=["eda", "results"], default=None)
    a = ap.parse_args()
    targets = {"eda": (EDA, HERE / "01_eda.ipynb"), "results": (RESULTS, HERE / "02_results.ipynb")}
    for key, (cells, path) in targets.items():
        if a.only and a.only != key:
            continue
        make(cells, path)
        if a.execute:
            execute(path)
        print("wrote", path)


if __name__ == "__main__":
    main()
