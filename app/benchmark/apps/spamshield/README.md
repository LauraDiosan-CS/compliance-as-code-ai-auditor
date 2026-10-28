# SpamShield

Inbound e-mail spam filter for the ACME corporate mail gateway. Postfix hands each message to the
SpamShield milter over mTLS; SpamShield returns `deliver`, `quarantine` or `tag`. Employees get a
daily quarantine digest and can release messages themselves.

* Model: TF-IDF (word + char n-grams) + Complement Naive Bayes, retrained monthly on
  employee-reported spam/ham.
* **AI Act:** minimal-risk system: spam filtering is not an Annex III use case, the system does not
  interact with people as a chatbot and does not generate content.
* Internal service only; no internet-facing endpoint.

## Run
```bash
python -m spamshield.server --config config/spamshield.yaml
```
