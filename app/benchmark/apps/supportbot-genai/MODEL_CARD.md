# Model card: SupportBot answer generation

* **Provider / model:** OpenAI `gpt-4o-mini` (API, EU data residency), pinned via `LLM_MODEL`.
* **Owner:** Customer Care Engineering (care-eng@acme.example).
* **Intended use:** answering customer questions on orders, deliveries, invoices and tariffs using
  retrieved help-centre extracts; handing over to a human agent.
* **Out of scope:** legal, financial or energy-saving advice; contract changes; complaints decisions.
* **Product evaluation (2026-08, 600 labelled conversations):** answer correctness 91.3%, grounded
  in retrieved context 95.0%, correct handover 88.0%, harmful/off-policy replies 0.3%.
* **Limitations:** may hallucinate tariff details not in the help centre; English and German only.
