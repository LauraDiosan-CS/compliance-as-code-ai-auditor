# Risk assessment and AI Act classification

## Classification
HireRight Screening is intended to "analyse and filter job applications, and to evaluate
candidates" and therefore falls under **Annex III, point 4(a)** of the AI Act. The Art. 6(3)
derogation does not apply: the ranking materially influences which candidates are reviewed first,
and the system profiles natural persons. **Result: high-risk.**

## Risk register (reviewed 2026-06-20)
| ID | Risk | Likelihood | Impact | Mitigation | Residual |
|---|---|---|---|---|---|
| R-01 | Recruiters over-rely on the ranking (automation bias) | medium | high | Ranking labelled as AI suggestion, reasons shown, decision requires explicit recruiter action and written reason for rejection, quarterly training | low |
| R-02 | Model degrades after market changes (drift) | medium | medium | PSI drift alerts, weekly performance report, yearly retraining | low |
| R-03 | Historical shortlisting bias reproduced (gender, age, origin proxies) | medium | high | Identity/protected fields removed; **group fairness evaluation pending (HR-412)** | medium (not accepted yet) |
| R-04 | CV parsing errors penalise unusual CV formats | medium | medium | Parse failures routed unranked to manual queue | low |
| R-05 | Unauthorised access to candidate data | low | high | OIDC auth, RBAC, KMS encryption, network policies | low |
| R-06 | Misuse for internal promotion decisions | low | high | Out-of-scope in model card and instructions; requisition id required | low |
