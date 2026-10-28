# Model risk management: CreditLens

## 1. Regulatory classification
Credit scoring of natural persons is listed in AI Act **Annex III, point 5(b)**; CreditLens is a
high-risk AI system. It is also in scope of the EBA guidelines on loan origination and monitoring.

## 2. Risk register
| ID | Risk | Mitigation | Owner |
|---|---|---|---|
| MR-1 | Discriminatory outcomes by age/gender/nationality proxies | Protected attributes excluded; quarterly fairness report with disparate-impact thresholds | CRA |
| MR-2 | Model drift after interest-rate changes | Monthly PSI and back-testing; challenger model | CRA |
| MR-3 | Over-reliance by underwriters | Reason codes shown; underwriter guide; 10% double review | Lending Ops |
| MR-4 | Erroneous automatic declines | Appeals process with 5-day SLA; monthly appeal-reversal review | Lending Ops |
| MR-5 | Data breach | KMS encryption, private networking, OAuth2 client credentials | Platform |

## 3. Change management
Model changes are classified minor/major. Major changes (new features, retraining, cutoff change
> 1 pp) need independent validation by Model Validation and approval by the Model Risk Committee.

## 4. Validation and monitoring
Pre-release: out-of-time test, stability tests, CI gate (`tests/test_quality_gate.py`).
Post-market monitoring: monthly performance report (AUC, Gini, default rate per score band), PSI
drift alerts, appeal reversal rate.

## 5. Incident reporting
Model incidents (wrong declines at scale, outages, discriminatory patterns) are logged in the
Operational Risk system within 24 hours and escalated to the Model Risk Committee; serious incidents
are reported to the AI Governance Board (ai-incidents@acme.example) and, where required, to the
competent authority.
