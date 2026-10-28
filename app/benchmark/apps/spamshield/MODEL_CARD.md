# Model card: SpamShield nb-2026.10

* **Owner:** Messaging Platform team (messaging@acme.example)
* **Model:** TF-IDF + Complement Naive Bayes (scikit-learn 1.5), version `nb-2026.10`.
* **Intended use:** classifying inbound e-mail to ACME mailboxes as spam / suspicious / legitimate.
* **Out of scope:** outbound mail, phishing attribution, any evaluation of employees.
* **Training data:** 1.2M messages reported as spam or released from quarantine by employees
  (rolling 12 months), message bodies normalised (URLs and addresses replaced by tokens).
* **Evaluation (October 2026 hold-out):** precision 0.991, recall 0.947, false-positive rate 0.04%.
* **Limitations:** weaker on image-only spam and on non-Latin scripts.
