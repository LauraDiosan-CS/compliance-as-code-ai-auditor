# Record of processing: inbound e-mail filtering (entry IT-SEC-03)

| Item | Content |
|---|---|
| Controller | ACME Corp, IT Security; DPO dpo@acme.example |
| Purpose | Protecting ACME mailboxes from spam and malicious e-mail |
| Lawful basis | Legitimate interest in IT security (Art. 6(1)(f) GDPR); balancing test IT-SEC-03-LIA |
| Data subjects | Senders and recipients of inbound e-mail |
| Personal data | E-mail headers and content; spam score; release actions |
| Recipients | None outside ACME IT Security / Messaging Platform |
| Retention | Quarantined messages 30 days; classification logs 180 days (message reference hash only) |
| Security | mTLS between gateway and filter, encrypted volumes (KMS), network policy |
