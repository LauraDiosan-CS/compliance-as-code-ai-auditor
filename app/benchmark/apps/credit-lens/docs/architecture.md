# CreditLens architecture

```
Loan origination platform ──OAuth2──► API Gateway (throttling) ──► creditlens (EKS, 3 pods)
                                                                   ├─ scoring.py (LightGBM + TreeSHAP reason codes)
                                                                   ├─ audit.py  ──► CloudWatch /creditlens/audit
                                                                   ├─ underwriting_queue / appeals_queue (SQS)
                                                                   └─ S3 acme-creditlens-applications (KMS)
```

* The service is stateless; application records are written by origination to S3 `records/`.
* Underwriters work in the origination back office, which reads the SQS queues.
* Model artefacts are baked into the container image; version reported in every response.
