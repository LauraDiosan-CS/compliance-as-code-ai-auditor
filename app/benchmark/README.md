# Benchmark: hand-labelled AI application repositories

Five small but realistic AI application repositories with hand-labelled ground truth for every curated
requirement of the three bundled policies (`eu-ai-act`, `gdpr`, `acme-rai`). The benchmark measures how
well the auditor's deterministic, LLM and hybrid modes reproduce a careful human audit
(accuracy / precision / recall / F1 per status, plus latency and cost).

```
app/benchmark/
├── apps/<app>/                 target repositories (code, configs, IaC, docs, model cards, sample logs)
├── ground_truth/<app>.json     {"app", "risk_level", "labels": {req_id: status}, "notes": {req_id: why}}
├── validate_corpus.py          validates policies, requirements YAML, clause ids, regexes and ground truth
└── label_stats.py              prints the label distribution tables below
```

Run `.venv/bin/python app/benchmark/validate_corpus.py` after editing any policy, requirement or label.

## The applications

| App | Domain | AI Act risk | Stack | Compliance profile |
|---|---|---|---|---|
| `hireright-screening` | CV ranking for recruiters | **high**, Annex III 4(a) | FastAPI, LightGBM + SHAP, React, k8s | Mostly compliant. Traceability through a custom `DecisionJournal.record(...)` on S3 Object Lock (no `logger` call); override and decision endpoints; kill switch named `suspend_automated_ranking`; model card, datasheet, Annex IV doc, risk register, privacy notice. Gaps: no bias evaluation, instructions for use have "TBD" performance/log sections, no ROPA, no DPIA. |
| `quickhire-ranker` | CV ranking startup MVP | **high**, Annex III 4(a) | Flask, XGBoost, React, Terraform | Mostly non-compliant: automatic rejection under a threshold, age/gender/nationality as features, CVs kept forever on an unencrypted EBS volume, no auth, no docs. |
| `supportbot-genai` | Customer-support chatbot (OpenAI SDK) | **limited** (Art. 50) | Express/TypeScript, React, RDS, k8s | AI disclosure banner in the React widget, rate limiting, KMS-encrypted DB, erasure endpoint, ROPA, incident runbook. Gaps: replies not labelled as AI-generated (only a TODO), transcripts kept 2 years (730 days), unredacted messages sent to the LLM, prediction logs kept only 90 days. |
| `credit-lens` | Consumer credit scoring | **high**, Annex III 5(b) | FastAPI, LightGBM, Terraform (KMS, S3, CloudWatch, API GW), k8s | Strong governance: DPIA, fairness report, model risk management, reason codes, appeals with underwriter reversal, kill switch, quality gates. Gaps: audit log group retention 30 days (< 6 months), automatic declines up to EUR 25,000 (human review only above), no instructions for use, no ROPA, partial technical documentation, no erasure procedure. |
| `spamshield` | Inbound e-mail spam filter | **minimal** | Python, scikit-learn, k8s | Most AI Act obligations not applicable. GDPR largely compliant (LIA, ROPA, privacy note, 30-day quarantine purge, mTLS, encrypted volume). Gaps: no AI incident procedure, no on-request erasure, no evidence of tamper-proof logs. |

### Deliberate difficulty for rule-based checks

Evidence was written the way real teams write it, not to match the curated regexes:

* **Indirect evidence (regex false negatives):** `DecisionJournal.record(...)` instead of `logger.info`
  (hireright), an admin route `suspend_automated_ranking` instead of a "kill switch" (hireright), a
  multi-line candidate notice (hireright), `pseudonymous` applicant refs and address tokenisation
  instead of the word "pseudonymise" (credit-lens, spamshield), training-data docs not named
  "datasheet" and a "model risk management" doc instead of a "risk assessment" (credit-lens), rights
  phrased as "the rights of access, ..." (spamshield), mTLS client certificates instead of RBAC
  helpers (spamshield).
* **Decoys (regex false positives):** a commented-out `# logger.info(f"prediction ...")` and
  `# TODO: add audit logging` (quickhire), `override_allowed = False` (quickhire), a README claiming
  "Fully GDPR compliant" and "Recruiters can always override the AI" (quickhire), a
  `TODO(SUP-88): label AI-generated replies` comment (supportbot), a docstring stating emotion
  recognition is *not* supported, which trips the Art. 5 "absent" rule (hireright), a smoke test that
  satisfies "tests exist" (quickhire), retention that is defined and enforced but disproportionate
  (supportbot), automatic declines named `decline` rather than `auto_reject` (credit-lens).
* **Requirements without checks** (`AIA-DATA-02`, `GDPR-ADM-01`, `ACME-11`) always need the LLM judge
  or a human.

## Labelling protocol

1. The risk level of each app was fixed first from its intended purpose (Annex III 4(a) recruitment,
   5(b) creditworthiness; Art. 50 chatbot; spam filter = minimal).
2. Each requirement was labelled by reading the whole repository against the requirement
   **statement** (and its `llm_guidance` where it clarifies thresholds), not by running the rules.
   Ground truth was written before the deterministic engine was run against the apps.
3. Status semantics:
   * `compliant`: every element of the statement is evidenced in the repository;
   * `partial`: some elements are evidenced and others are missing or insufficient
     (e.g. logging present but retention below the threshold, human review only above an amount);
   * `non_compliant`: no credible evidence, or evidence of the opposite (e.g. auto-rejection);
   * `not_applicable`: used **only** when the requirement's `applies_to` excludes the app's risk level,
     exactly as `rules.engine.evaluate_all` does, so N/A is never a judgement call;
   * `needs_review` is not used in the ground truth (it is a model output, not a truth value).
4. Claims without backing (README marketing, TODOs, commented code, plans) are not evidence.
   Documents count as evidence for documentation requirements; code/IaC/config for technical ones.
5. Every applicable label has a short justification with file references in `notes`.
6. Scoping simplifications (documented in the YAML headers): AI Act Art. 50 requirements are scoped
   to `limited`; GDPR Art. 22 / Art. 35 and ACME POL-7 / POL-11 to `high`; ACME POL-2 to `limited`.

## Label distribution

Generated with `.venv/bin/python app/benchmark/label_stats.py` (45 requirements x 5 apps):

| App | Risk | compliant | partial | non_compliant | needs_review | not_applicable | total |
|---|---|---:|---:|---:|---:|---:|---:|
| credit-lens | high | 32 | 7 | 3 | 0 | 3 | 45 |
| hireright-screening | high | 37 | 1 | 4 | 0 | 3 | 45 |
| quickhire-ranker | high | 1 | 2 | 39 | 0 | 3 | 45 |
| spamshield | minimal | 15 | 2 | 1 | 0 | 27 | 45 |
| supportbot-genai | limited | 15 | 2 | 4 | 0 | 24 | 45 |
| **all** | | **100** | **14** | **51** | **0** | **60** | **225** |

| Policy | compliant | partial | non_compliant | needs_review | not_applicable | applicable |
|---|---:|---:|---:|---:|---:|---:|
| eu-ai-act | 42 | 3 | 24 | 0 | 46 | 69 |
| gdpr | 30 | 5 | 14 | 0 | 6 | 49 |
| acme-rai | 28 | 6 | 13 | 0 | 8 | 47 |

## Policy evolution demo

`data/policies/acme-responsible-ai-policy.v2.md` (same id `acme-rai`, version "2") changes POL-2(2)
(SHOULD to MUST), POL-3(2) (log retention 180 to 365 days), POL-7 (all significant decisions, no amount
threshold, new four-eyes paragraph POL-7(3)) and adds POL-12 (GenAI watermarking). Diffing v1 and v2
should flag `ACME-02`, `ACME-03` and `ACME-07` as affected, and reports for hireright (journal kept 400
days, still compliant) vs credit-lens (30 days) show different impact. Requirements are only curated for
v1 (`requirements/acme-rai.yaml`); a v2 requirements file is intentionally not provided because the
loader merges all YAML files with the same `policy_id`.

## Evaluation

```
.venv/bin/python app/benchmark/evaluate.py --out v0_baseline --modes deterministic,hybrid,llm --model sonnet
.venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --model haiku --append
.venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --hybrid-threshold 1.01 --append  # route all
.venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --no-verifier --append          # ablation
.venv/bin/python app/benchmark/evaluate.py --out v1_improved --modes hybrid --verify-llm --append           # ablation
.venv/bin/python app/benchmark/threshold_sweep.py --run v1_improved --model sonnet                         # LOAO routing threshold
```

Every run audits the 5 apps against all 3 policies and writes `results/<run>.json` (metrics + per-item
predictions), the full reports `results/<run>/reports/<app>__<config>.json`, confusion matrices
`results/<run>/confusion_<config>.csv`, and rebuilds `results/SUMMARY.md`. Metric definitions are in the
`evaluate.py` docstring; in short, accuracy/macro-F1 are on the 165 applicable labels (needs_review and wrong
N/A count as errors), *gap detection* treats partial|non_compliant as positive (needs_review counts as
flagged), and the *false-compliance rate* is P(predicted compliant | truth partial or non_compliant), the
critical failure for an auditor. Costs are the `total_cost_usd` reported by the Claude Code CLI (equivalent
API price; the runs used a subscription), including cached calls at their original cost.
Analysis and figures: `app/notebooks/02_results.ipynb`, `docs/report/figures/results_*.pdf`.

### v0 (baseline) vs v1 (improved)

| run | config | acc | macro-F1 | gap R | gap P | false-compl. | needs_review | acc@deferral | risk acc | LLM calls | cost $ | est. s/app |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0 | deterministic | 79.4 | 72.3 | 87.7 | 78.1 | 12.3 | 5.5 | 84.0 | 80 | 0 | 0.00 | <1 |
| v0 | hybrid-sonnet | 86.1 | 77.1 | 87.7 | 83.8 | 12.3 | 0.0 | 86.1 | 100 | 23 | 0.67 | 25 |
| v0 | llm-sonnet | 71.5 | 67.6 | 100.0 | 60.8 | 0.0 | 0.6 | 72.0 | 100 | 170 | 4.81 | 94 |
| v1 | deterministic | 82.4 | 74.9 | 93.8 | 80.3 | 6.2 | 5.5 | 87.2 | 100 | 0 | 0.00 | <1 |
| v1 | **hybrid-sonnet** (t=0.675) | **94.5** | **86.6** | 96.9 | **96.9** | 3.1 | 0.6 | 95.1 | 100 | 103 | 2.77 | 50 |
| v1 | hybrid-sonnet-all (t>1) | 90.9 | 82.1 | 98.5 | 87.7 | 1.5 | 0.6 | 91.5 | 100 | 170 | 4.82 | 90 |
| v1 | llm-sonnet | 90.9 | 83.1 | 100.0 | 85.5 | 0.0 | 0.6 | 91.5 | 100 | 170 | 4.68 | 91 |
| v1 | hybrid-haiku | 83.6 | 75.4 | 96.9 | 76.8 | 3.1 | 5.5 | 88.5 | 100 | 103 | 0.19 | 75 |
| v1 | llm-haiku | 71.5 | 66.7 | 100.0 | 61.9 | 0.0 | 7.3 | 77.1 | 100 | 170 | 0.32 | 116 |
| v1 | hybrid-sonnet, no Verifier | 94.5 | 86.6 | 96.9 | 96.9 | 3.1 | 0.6 | 95.1 | 100 | 103 | 2.77 | 50 |
| v1 | hybrid-sonnet + LLM claim verifier | 88.5 | 83.1 | 96.9 | 85.1 | 3.1 | 6.7 | 94.8 | 100 | 156 | 3.89 | 89 |

Citation validity was 100% in every configuration (all cited evidence ids exist), and every LLM-involved
compliant verdict cites at least one evidence item.

### Changes between v0 and v1 (all general, no benchmark file or label was edited)

1. **Rules engine: comment-aware matching** (`rules/comments.py`). Pattern checks run on text where comments,
   docstrings and TODO/FIXME/TBD lines are blanked (line numbers preserved; Python via `tokenize`, C-like / hash /
   HCL / SQL / markup comment syntaxes via a string-aware scanner). Commented-out code and TODOs are non-evidence
   (a strong-ish negative, 0.75); explanatory prose comments/docstrings are a weak *claim* (pass at 0.55, which
   hybrid routes to the LLM); switched-off flags (`*_allowed = False`) do not satisfy "present" checks; "absent"
   checks ignore comments entirely. Effect (deterministic): 4 decoy false compliants removed (quickhire logging and
   override, supportbot AI-label TODO x2) and the docstring false alarm on Art. 5 fixed.
   An intermediate version that simply discarded all comment matches lost 3 true compliants whose only keyword was
   an explanatory comment next to real fail-safe / mTLS code, hence the prose-vs-code distinction.
2. **Graded rule confidence** instead of fixed 0.9/0.8/0.5/0.2: per-check strength from the number of matching
   lines/files, evidence kind (a technical check satisfied only by documentation = claim, 0.55), and check type
   (regex miss 0.6, "absent" pass 0.6, file exists 0.7, ...).
3. **Hybrid routing / arbitration** (`pipeline.py`): threshold on the graded confidence chosen by
   leave-one-app-out (`threshold_sweep.py`: every fold picks 0.625-0.675; median 0.675; pooled held-out
   accuracy 93.3% vs 94.5% in-sample), so ~60% of applicable items get an LLM second opinion. On hard
   rules-vs-LLM disagreement the side that is >= 0.15 more confident wins (confidence -0.1), otherwise
   needs_review.
4. **Risk heuristic** (`agents/risk.py`): negated mentions are ignored ("does not interact with people as a
   chatbot"), signals are weighted (self-description in README / model card 2.0, other docs 1.0, code 0.5 and
   code alone capped at 1.0), a tier needs a score >= 2. spamshield is now minimal (was limited), heuristic risk
   accuracy 80% -> 100%, which also fixes 3 wrong applicability decisions in deterministic mode.
5. **Judge prompt** (`agents/judge.py`): the v0 LLM errors were 41/47 compliant -> partial (perfectionism:
   demanding things the statement does not require, or penalising excerpts truncated at the chunk boundary).
   The rubric now states the documented labelling protocol: the statement is the test, truncation is not a gap,
   claims/TODOs are not evidence, explicit compliant / partial / non_compliant semantics (a missing artefact is
   non_compliant even if fragments exist elsewhere). llm-sonnet accuracy 71.5% -> 90.9%.

### Ablations and findings

* **Verifier off**: identical results for sonnet and haiku: with short evidence aliases (E1, E2, ...) and JSON
  schema output neither model ever cited a non-existent id on this benchmark, so the deterministic Verifier is a
  safety net that did not trigger (it is covered by unit tests with injected bad citations).
* **LLM claim-support verifier** (`--verify-llm`): +53 calls, needs_review 0.6% -> 6.7%, accuracy 94.5% -> 88.5%,
  false-compliance unchanged (3.1%): it mostly defers verdicts that were correct. Not worth it here.
* **haiku vs sonnet**: hybrid-haiku costs 15x less ($0.19 vs $2.77 for the 5 apps) but loses 11 points of
  accuracy; llm-haiku is no better than v0 llm-sonnet (still compliant -> partial heavy). The rules + routing
  give haiku most of its accuracy.
* **Remaining hybrid-sonnet errors (9/165)**: 5 at the partial / non_compliant boundary (erasure: automatic
  expiry but no on-request process; human review only above EUR 25,000), 2 high-confidence rule passes where
  only the proportionality of a value decides (2-year transcript retention, logs without tamper protection),
  1 compliant -> partial, 1 rules-vs-LLM disagreement deferred to review.

### Caveats

* 5 apps / 165 applicable labels written by the same team that built the auditor: confidence intervals are
  wide (+/- ~4 points at 95% for accuracy around 0.9) and the benchmark is not a held-out test set.
* The v1 changes were designed after inspecting v0 errors on these same apps (and the prose-comment rule after
  inspecting a v1 intermediate), so v1 numbers carry tuning bias even though no change refers to a specific
  file. The routing threshold is the only tuned parameter and is reported with leave-one-app-out.
* LLM outputs are cached by prompt hash; reruns are deterministic, a cold rerun could differ slightly.
