# SupportBot

Customer-support assistant for the ACME Home Energy web shop. The widget answers questions about
orders, deliveries, invoices and tariffs using an LLM (OpenAI `gpt-4o-mini`) grounded on our help
centre articles, and hands over to a human agent on request.

## AI Act position
SupportBot is a chatbot that interacts directly with customers. It does not take decisions about
people and is not in any Annex III area, so it is a **limited-risk** system: the transparency
obligations of Art. 50 apply (users must know they are talking to an AI).

## Layout
| Path | |
|---|---|
| `server/` | Express + TypeScript API (`/api/chat`, admin transcript tools) |
| `web/` | Chat widget (React) embedded in the shop |
| `config/app.yaml` | rate limits, retention, model settings |
| `infra/` | Terraform (RDS Postgres) and Kubernetes manifests |
| `docs/` | privacy notice, record of processing, incident response, ADRs |
