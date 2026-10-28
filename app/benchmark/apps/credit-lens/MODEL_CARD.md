# Model card: pd-lgbm-3.1.0

* **Owner:** Credit Risk Analytics (cra@acme-finance.example)
* **Type:** LightGBM binary classifier, probability of default within 12 months.
* **Intended use:** consumer personal-loan applications, EUR 1,000-75,000, EU retail customers.
* **Out of scope:** mortgages, business lending, collections prioritisation, fraud detection.
* **Training data:** 1.9M applications 2018-2023 with 12-month performance (`docs/data/training-data.md`).
* **Performance (out-of-time test 2024):** ROC-AUC 0.81, Gini 0.62, KS 0.47; calibration error 0.6 pp.
* **Fairness:** see `docs/fairness-report-2026Q2.md`.
* **Limitations:** thin-file applicants (no bureau history) have lower accuracy (AUC 0.72); not
  validated for applicants under 21.
