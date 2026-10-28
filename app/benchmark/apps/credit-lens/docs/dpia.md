# DPIA: automated credit scoring (CreditLens)

## 1. Description of the processing
Evaluation of creditworthiness of loan applicants using a statistical model fed by application data
and credit-bureau data; automatic approval/decline for amounts up to EUR 25,000, underwriter review
above. Data subjects: loan applicants. Recipients: ACME lending staff, credit bureau (inquiry).

## 2. Necessity and proportionality
Lawful basis: Art. 6(1)(b) (steps prior to contract) and Art. 6(1)(c) (creditworthiness assessment
required by the Consumer Credit Directive). Automated decisions rely on Art. 22(2)(a); safeguards:
appeal with human re-assessment, right to express a point of view. Only financial and employment
data are used; no special categories.

## 3. Risks to rights and freedoms
* Unjustified declines and financial exclusion; indirect discrimination; opacity of the score;
  breach of financial data.

## 4. Measures
Appeals (5-day SLA), reason codes in decline letters, quarterly fairness report, KMS encryption,
pseudonymous applicant references, access via OAuth2 scopes.

## 5. Residual risk
Medium-low; accepted by DPO and Head of Lending on 2026-04-14.

## 6. Retention
Raw request payloads 30 days; application records 5 years after contract end or decline (legal
obligation under national consumer credit and AML law).
