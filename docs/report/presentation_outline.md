# Compliance-as-Code AI Auditor: final presentation

AML 2026-2027, Bâlc Felicia, Drăghici Eduard, Gog Raluca.
Slot: 15 minutes, followed by Q&A. Times are cumulative. Speakers are a proposal; change them as needed.

## Talk outline (15 min)

| # | Time | Slide | Content | Speaker |
|---|---|---|---|---|
| 1 | 0:00-0:45 | Title + hook | "Would you sign this AI Act audit?" Show a README that says "Fully GDPR compliant" next to a commented-out `# logger.info(...)`. | FB |
| 2 | 0:45-2:00 | Problem | The AI Act has risk tiers (Art. 5 / Annex III / Art. 50) and obligations in Arts. 9-15. Evidence is spread over code, IaC, configs, docs and model cards. Manual audits are slow and go stale. Rules are shallow and LLMs hallucinate. | FB |
| 3 | 2:00-3:00 | Formalisation | P → clauses C → requirements R; repo → evidence E; f: R × 2^E → status × confidence × citations. Constraints: applicability, grounding, no unsupported compliance. Abstention (needs_review) is allowed. | ED |
| 4 | 3:00-3:45 | Graphical abstract | Walk through the pipeline figure once from left to right. | ED |
| 5 | 3:45-5:30 | Hybrid orchestration | Rule engine first. The judge gets a requirement when the rule confidence is below τ=0.75, the rules say partial or needs_review, or the requirement has no checks. Conflicts and confidence below β=0.6 go to a human. Show Algorithm 1. | ED |
| 6 | 5:30-6:30 | Verifier | The judge cites evidence by alias (E1, E2, ...). The verifier drops ids that were never shown and turns "compliant" without a valid citation into needs_review. An optional LLM support check runs on top. Show Algorithm 2. | ED |
| 7 | 6:30-7:30 | Benchmark | 5 apps across the risk tiers, 225 labels (165 applicable). It includes traps: indirect evidence, decoys, and requirements with no rules. | RG |
| 8 | 7:30-9:30 | Results | Main table with accuracy, macro-F1, gap P/R, false-compliance rate, needs_review rate, LLM calls, $ and seconds. Add the cost-quality plot. **[fill from results]** | RG |
| 9 | 9:30-10:15 | Ablations | Verifier on/off, LLM support check, Sonnet vs Haiku, routing threshold, cold vs warm cache. **[fill]** | RG |
| 10 | 10:15-12:00 | Live demo (or recorded) | Dashboard: run a hybrid audit on `credit-lens`. Show the overview gauge, a gap with `file:line` evidence (30-day log retention), the review queue with one human decision, the traceability tab, and SARIF in CI. | RG + ED |
| 11 | 12:00-13:15 | Governance | Agency table (autonomous / human / never). Required components: retrieval, no tools, no memory, fixed orchestration, checks. Accountability: the record, named reviewers, how to contest. | FB |
| 12 | 13:15-14:15 | SWOT + sustainability | SWOT quadrant. Routing, bounded prompts and the cache keep calls and tokens low. | FB |
| 13 | 14:15-15:00 | Conclusions | Three takeaways: (1) rules and LLMs fail in different, complementary ways; (2) false compliance can be controlled by structure; (3) an auditor must itself be auditable. End with future work. | all |

Backup slides: label distribution, per-category accuracy, the worked example (AIA-REC-01 on hireright), metric definitions, prompts.

Likely questions to prepare for:
- Why BM25 and not embeddings?
- How is the judge's confidence calibrated?
- Who is liable when the tool is wrong?
- What about confidential code being sent to a hosted LLM?
- How big is the gap between the benchmark and real repositories?
- Why is hybrid worse than LLM on X? (once results are in)

## Teaser video script (~60 s)

| Time | Visual | Voice-over |
|---|---|---|
| 0-6 s | Black screen; the text "EU AI Act: 113 articles. Your repo: 4,000 files." appears. | "The EU AI Act is here. Is your AI system compliant? Can you prove it?" |
| 6-15 s | Split screen: a README saying "Fully GDPR compliant"; the code underneath has a commented-out logger. | "Documents make claims. Code tells the truth. Checking one against the other by hand takes weeks, and has to be redone after every commit." |
| 15-28 s | The graphical abstract animates: policy → requirements, repo → evidence, rules → LLM judge → verifier → human. | "Our Compliance-as-Code AI Auditor turns regulations into testable requirements. Fast rules check what is precise. Claude judges the rest from retrieved evidence. A verifier rejects any 'compliant' that lacks a real citation." |
| 28-42 s | Screen recording of the dashboard: score gauge, then a gap opened with file:line evidence, then the review queue. | "Every verdict links to the exact file and lines, or to a gap and a fix. When the rules and the AI disagree, a human decides, and that decision is recorded." |
| 42-52 s | Results chart (accuracy, false-compliance rate, cost per audit). **[fill numbers]** | "On five hand-labelled AI applications, the hybrid mode reaches [X]% accuracy at [Y] dollars per audit, with [Z]% false compliance." |
| 52-60 s | Logo, title, team names, "AML 2026-2027, UBB Cluj". | "Compliance you can check, cite and contest. Compliance-as-Code AI Auditor." |
