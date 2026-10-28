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
