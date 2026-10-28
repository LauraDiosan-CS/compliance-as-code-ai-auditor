# AI incident response

1. **Detect:** alerts on harmful-reply classifier hits, spikes in handover rate, customer complaints
   tagged `ai-answer`.
2. **Contain:** on-call engineer can switch the widget to "human agents only" via the feature flag
   `chat.ai_enabled`.
3. **Escalate:** notify Customer Care lead and #supportbot-incidents.
4. **Report:** serious incidents (harmful or discriminatory output, personal data leak through the
   model) are reported to the AI Governance Board at ai-incidents@acme.example within 24 hours;
   personal data breaches also go to the DPO for the 72-hour GDPR assessment.
5. **Review:** blameless post-mortem within 10 working days.
