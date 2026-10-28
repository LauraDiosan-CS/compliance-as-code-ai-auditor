# HireRight Screening

HireRight Screening ranks incoming job applications for ACME Talent Acquisition so recruiters can
prioritise their review queue. The model reads the parsed CV and the job requisition and produces a
relevance score (0-1) plus the main reasons behind it. **Recruiters take every decision**; the
system never rejects or advances a candidate on its own.

## Regulatory position

* EU AI Act: **high-risk AI system** under Annex III, point 4(a) (AI systems intended to be used to
  analyse and filter job applications and to evaluate candidates). ACME acts as provider and deployer.
  See `docs/risk-assessment.md` for the classification rationale and the risk register.
* GDPR: ACME is controller; candidates are informed through `docs/privacy-notice.md`.

## Components

| Path | Purpose |
|---|---|
| `src/hireright/api.py` | FastAPI service: scoring, reviewer decisions, admin controls, erasure |
| `src/hireright/model.py` | Gradient-boosted ranker + per-candidate explanations |
| `src/hireright/journal.py` | `DecisionJournal`, append-only record of every score and human action |
| `src/hireright/retention.py` | Nightly purge of raw CVs and expired journal segments |
| `web/` | Recruiter dashboard (React) |
| `infra/k8s/` | Deployment manifests (EKS) |

## Documentation

* `MODEL_CARD.md`, `DATASHEET.md`
* `docs/technical-documentation.md` (Annex IV structure)
* `docs/instructions-for-use.md` (for recruiting teams)
* `docs/release-process.md` (change management, monitoring, incidents)

## Running locally

```bash
pip install -e .
uvicorn hireright.api:app --reload
```
