# Training data: pd-lgbm-3.1.0

* **Origin:** ACME loan book 2018-2023 (1.9M applications) joined with 12-month repayment outcomes
  and bureau attributes at application time (contracted bureau, purpose: credit risk modelling).
* **Collection purpose:** creditworthiness assessment; model development is compatible further
  processing (assessment of 2024-01-10).
* **Preparation:** exclusion of fraud-flagged applications (0.8%); winsorisation of income at
  P99.5; missing bureau data imputed with a "thin file" indicator; reject inference via
  fuzzy augmentation for declined applications.
* **Splits:** train 2018-2022, validation 2023-H1, out-of-time test 2023-H2/2024.
* **Assumptions:** 90+ days past due within 12 months as default definition; macro conditions of
  2018-2023 representative for the next 2 years.
* **Known gaps:** few applicants under 21 and over 75; self-employed under-represented (6%).
