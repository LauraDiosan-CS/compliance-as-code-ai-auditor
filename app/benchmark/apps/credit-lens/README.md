# CreditLens

Credit scoring service for ACME Consumer Finance personal loans (EUR 1,000 to 75,000). The loan
origination platform calls `POST /v1/score` with the application; CreditLens returns a probability
of default, a decision recommendation and adverse-action reason codes.

* **AI Act:** high-risk, Annex III point 5(b) (creditworthiness evaluation of natural persons).
  Rationale and risk register in `docs/model-risk-management.md`.
* **GDPR:** DPIA in `docs/dpia.md`; applicant information in `docs/applicant-notice.md`.

## Decision flow
1. Applications above `manual_review_threshold_eur` always go to an underwriter.
2. Smaller applications are approved or declined automatically from the score.
3. Applicants can contest any decision via `POST /v1/appeals`; an underwriter re-assesses the file.

## Repository
`service/` FastAPI app, `infra/terraform` AWS (KMS, S3, CloudWatch, API Gateway), `infra/k8s`
manifests, `tests/` quality gates, `docs/` governance documents.
