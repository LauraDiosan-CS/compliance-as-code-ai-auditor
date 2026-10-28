# ADR 0001: Use a hosted LLM with retrieval instead of fine-tuning

* Status: accepted (2026-02-11)

We use OpenAI `gpt-4o-mini` through the API with EU data residency and zero data retention on the
provider side, grounded with help-centre extracts (top-4 BM25 + embeddings). Fine-tuning was
rejected: help-centre content changes weekly. Customer messages are sent to the provider as typed;
redaction of contact details was evaluated but postponed because it reduced answer quality for
delivery questions.
