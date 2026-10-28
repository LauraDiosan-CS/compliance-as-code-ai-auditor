# Release process and quality management

## Change management
Every change to the model, features, thresholds or UI text goes through a pull request with two
approvals (one from Talent Data Science, one from Talent Technology). Model releases additionally
require sign-off by the AI Governance Board representative. Release notes record the model version
and the evaluation report.

## Validation before release
1. Offline evaluation on the frozen hold-out set; CI gate `tests/test_model_quality.py`
   (ROC-AUC >= 0.85, NDCG@10 >= 0.68).
2. Two-week shadow deployment: new model scores in parallel, rankings not shown.
3. Go/no-go meeting with recruiting leads.

## Post-market monitoring
* Weekly performance report: shortlist rate per score decile, override rate, unranked rate.
* Drift: PSI on top-20 features, alert at 0.2 (PagerDuty `hireright-ml`).
* Quarterly review of overrides with recruiting leads.

## Incident reporting
AI incidents (discriminatory behaviour, data leak, severe degradation) are raised in
#hireright-incidents, triaged by the on-call ML engineer and reported to the AI Governance Board
(ai-incidents@acme.example) within 24 hours. Serious incidents under AI Act Art. 73 are notified to
the market surveillance authority by Legal.
