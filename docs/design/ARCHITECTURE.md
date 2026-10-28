# Compliance-as-Code AI Auditor: Architecture

Team: Bâlc Felicia, Drăghici Eduard, Gog Raluca. AML 2026-2027, topic #5.

## Goal
Input: a policy/regulation (EU AI Act, GDPR, internal policy) + an application repository.
Output: an auditable compliance report that links **every requirement** to **evidence** (file + lines) or to a **gap**,
with a scorecard per category, risk-level classification, and remediation suggestions.

## Pipeline
```
Policy text (.md) ──► Ingestion ──► Clauses ──► Decomposition ──► Requirements (+ deterministic checks)
                                                 (curated YAML or LLM agent)
Target repo ──► Evidence collectors (code/config/IaC/docs/model cards/logs) ──► EvidenceIndex (+ BM25 retriever)
Requirements × Evidence ──► Evaluation:
      deterministic  : YAML/Rego rule engine only
      llm            : LLM judge agent with retrieved evidence
      hybrid         : rules first, LLM for ambiguous/unknown, Verifier checks every citation
 ──► Verdicts ──► low confidence / conflicting → NEEDS_REVIEW (human-in-the-loop queue)
 ──► Report (JSON / Markdown / SARIF / web dashboard) + scorecard
```

## Agents (agentic orchestration)
| Agent | Responsibility |
|---|---|
| PolicyAnalyst | clauses → verifiable `Requirement`s (category, statement, retrieval queries, guidance) |
| RiskClassifier | classifies the app as prohibited/high/limited/minimal (Art. 5, Art. 6 + Annex III, Art. 50) |
| EvidenceScout | expands retrieval queries, selects the most relevant evidence per requirement |
| ComplianceJudge | decides status + rationale + gaps, **must cite evidence ids** |
| Verifier | anti-hallucination: checks cited ids exist and snippets support the claim; downgrades unsupported claims |
| Remediator / ArtifactGenerator | remediation text, drafts missing artefacts (tech-doc section, risk assessment template) |
| Orchestrator | plans the run, routes deterministic vs LLM, aggregates, enforces HITL for borderline |

LLM backend: **Claude Code CLI in headless mode** (`claude -p --output-format json`), using the
developer's Claude subscription, so no API key is needed. `FakeBackend` gives deterministic tests.

## Package layout (`app/backend/ccauditor`)
```
models.py                 shared contracts (DO NOT change field names without updating all users)
policies/loader.py        load_policy(path)->Policy ; load_requirements(path)->list[Requirement] ; list_builtin_policies()
policies/evolution.py     diff_policies(old, new, requirements)->impact report
evidence/collector.py     collect(repo_root, exclude=None)->EvidenceIndex
evidence/retriever.py     Retriever(index).search(query, k=8, kinds=None)->list[Evidence]
evidence/files.py         safe file walking/reading helpers
rules/engine.py           evaluate_requirement(req, repo_root, index)->Verdict  (method="deterministic")
report/scoring.py         build_scorecard(requirements, verdicts)->(list[CategoryScore], float)
report/render.py          to_json(report), to_markdown(report), to_sarif(report)
llm/backend.py            LLMBackend protocol; ClaudeCodeBackend; FakeBackend
agents/*.py               agents above
pipeline.py               run_audit(repo_root, policy_ids, mode, backend=None, ...)->AuditReport
ci.py                     changed-files scan + regression detection vs baseline report
cli.py                    `ccauditor audit|policies|diff-policy|ci|review`
api.py                    FastAPI app
data/policies/*.md        policy corpora   data/requirements/*.yaml curated requirements + rules
```

## Policy markdown format
```
---
id: eu-ai-act
name: EU AI Act (Regulation (EU) 2024/1689), selected provisions
version: "2024-07-12"
kind: regulation
source: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
---
## Art. 12 | Record-keeping            -> Clause id "eu-ai-act/Art.12"
### 1                                  -> Clause id "eu-ai-act/Art.12(1)", parent "eu-ai-act/Art.12"
text...
```

## Requirements YAML format
```yaml
policy_id: eu-ai-act
requirements:
  - id: AIA-REC-01
    clause_ids: ["eu-ai-act/Art.12(1)"]
    category: record_keeping
    title: Automatic logging of AI decisions
    statement: The system automatically records events (inputs, outputs, timestamps) for each model decision.
    applies_to: [high]
    severity: high
    evidence_queries: ["logging", "audit log", "logger.info prediction"]
    llm_guidance: Look for logging of model inputs/outputs with timestamps...
    checks:
      - type: pattern
        kinds: [code]
        pattern: "(audit_log|logger\\.(info|warning)).*(predict|decision|output)"
        expect: present
```

## Benchmark (`app/benchmark`)
Small, deliberately varied AI applications with hand-labelled ground truth per requirement,
used to measure precision/recall/F1/accuracy of deterministic vs LLM vs hybrid, plus latency & cost.
