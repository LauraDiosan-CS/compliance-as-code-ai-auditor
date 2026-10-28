# Fairness report Q2 2026 (pd-lgbm-3.1.0)

Protected attributes are not model inputs; they were joined from the KYC system for evaluation only
(Art. 10(5) AI Act safeguards: segregated environment, deleted after analysis).

| Group | Approval rate | Disparate impact vs reference | Default rate (approved) | AUC |
|---|---|---|---|---|
| Women (ref: men) | 61.8% vs 63.1% | 0.98 | 2.9% vs 3.1% | 0.81 / 0.81 |
| Age 21-29 (ref: 30-59) | 52.4% vs 64.0% | 0.82 | 4.1% vs 2.8% | 0.78 / 0.82 |
| Age 60+ (ref: 30-59) | 66.2% vs 64.0% | 1.03 | 2.2% vs 2.8% | 0.80 / 0.82 |
| Non-national residents (ref: nationals) | 55.1% vs 63.5% | 0.87 | 3.6% vs 3.0% | 0.79 / 0.81 |

**Findings.** All groups above the 0.80 disparate-impact threshold. Age 21-29 near the threshold,
driven by `months_at_employer`; mitigation: capped contribution of `months_at_employer` for applicants
with education completed < 3 years ago (shipped in 3.1.0), monitored monthly.
