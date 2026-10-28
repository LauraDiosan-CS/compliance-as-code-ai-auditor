# ADR 0002: DecisionJournal instead of application logs for traceability

* Status: accepted (2025-09-18)

## Context
We need a reliable trace of every ranking and every human action (AI Act Art. 12, 19 and 26(6)).
Application logs are sampled, mutable and expire after 14 days in our logging platform.

## Decision
Introduce `DecisionJournal` (`src/hireright/journal.py`): one JSON entry per event (`ranked`,
`reviewer_decision`, `override`, `suspended`, `resumed`) with model version, input digest, result and
actor, written to an S3 bucket with Object Lock in compliance mode. Retention: 400 days
(`config/retention.yaml`). CV content is never written to the journal; only a SHA-256 digest.

## Consequences
* Auditors can reconstruct who saw which ranking and what was decided.
* Journal lines are not visible in Kibana; a small Athena view is provided for investigations.
