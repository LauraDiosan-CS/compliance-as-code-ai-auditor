# Datasheet: HireRight ranking dataset v5

## 1. Motivation
Built to train and evaluate the candidate ranker (`MODEL_CARD.md`).

## 2. Composition
* 512,340 (application, requisition, label) triples; 38,912 requisitions; 14 EU countries.
* Label: 1 if a recruiter shortlisted the application, else 0.
* Splits: train 2021-01..2024-12 (80%), validation 2025-H1 (10%), test 2025-H2 (10%), split by
  requisition to avoid leakage.

## 3. Collection and personal data
* Source: ACME ATS (Workday) exports; original purpose of collection: recruitment for the
  advertised role. Re-use for model development assessed in the LIA of 2025-11-03.
* Removed before storage in the training bucket: name, e-mail, phone, photo, date of birth, gender,
  nationality, address. Candidate ids are replaced by salted hashes.

## 4. Preparation
* CV parsing with `cvparse 3.2`; documents failing parsing (4.1%) were dropped.
* Deduplication of re-applications within 30 days; skill normalisation against ESCO v1.2.
* Label noise review on a 2,000-sample audit (agreement 0.91).

## 5. Assumptions and known gaps
* Assumes recruiter shortlisting is a reasonable proxy for relevance.
* Under-representation of applications for engineering roles in DE/AT before 2023.
* Bias examination: not yet performed on this version (ticket HR-412, planned for Q4 2026).

## 6. Maintenance
Refreshed yearly by Talent Data Science; versions stored in `s3://acme-hireright-datasets/`.
