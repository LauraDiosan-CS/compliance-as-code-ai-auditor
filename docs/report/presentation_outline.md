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
| 5 | 3:45-5:30 | Hybrid orchestration | Rules run first with graded confidence: a regex miss counts 0.6, a docs-only claim 0.55, and comments and TODOs are not evidence. The judge gets every item with rule confidence below τ=0.675; τ was chosen by leave-one-app-out and covers about 60% of the items. On a rules-vs-LLM conflict, the side that is at least 0.15 more confident wins, otherwise a human decides; the human gate also takes anything below β=0.6. Show Algorithm 1 and the worked example AIA-REC-01: v0 kept a wrong NC, v1 routes it and the judge wins 0.88 vs 0.60. | ED |
| 6 | 5:30-6:30 | Verifier | The judge cites evidence by alias (E1, E2, ...). The verifier drops ids that were never shown and turns "compliant" without a valid citation into needs_review. An optional LLM support check runs on top. Show Algorithm 2. | ED |
| 7 | 6:30-7:30 | Benchmark | 5 apps across the risk tiers, 225 labels (165 applicable). It includes traps: indirect evidence, decoys, and requirements with no rules. | RG |
| 8 | 7:30-9:30 | Results | Hybrid-Sonnet: 94.5% accuracy (CI 90.9-97.6), 86.6 macro-F1, gap P/R 96.9/96.9, FCR 3.1%, 0.6% needs_review, 103 calls, $2.77 for 5 apps, 50 s/app. LLM-Sonnet: 90.9%, FCR 0%, 170 calls, $4.68, 91 s/app. Deterministic: 82.4%, $0, 0.2 s/app. Hybrid vs deterministic McNemar p=3.6e-5; hybrid vs LLM p=0.21. Show the cost-quality plot and the confusion matrices. Citation validity 100% everywhere. | RG |
| 9 | 9:30-10:15 | v0 to v1 + ablations | v0 baseline: hybrid 86.1%, LLM 71.5%; 41 of 47 LLM errors were over-strict "partial" labels. Fixes: comment-aware rules, graded confidence, LOAO threshold, rubric prompt. Ablations: Verifier off gives identical results (it never had to fire); the LLM claim check adds 53 calls and lowers accuracy to 88.5%; Haiku is 15x cheaper but scores 83.6%; routing everything gives 90.9%, worse than routing 59%. A warm re-audit makes 0 calls and takes 0.3 s. | RG |
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
- Why does hybrid still miss 2 gaps when LLM-only misses none? (Proportionality: rules pass a 2-year retention period with high confidence.)
- Is v1 tuned on the test set? (Yes, partly. The only tuned parameter, τ, is reported with leave-one-app-out: 93.3% held-out vs 94.5% in-sample.)

## Teaser video script (~60 s)

| Time | Visual | Voice-over |
|---|---|---|
| 0-6 s | Black screen; the text "EU AI Act: 113 articles. Your repo: 4,000 files." appears. | "The EU AI Act is here. Is your AI system compliant? Can you prove it?" |
| 6-15 s | Split screen: a README saying "Fully GDPR compliant"; the code underneath has a commented-out logger. | "Documents make claims. Code tells the truth. Checking one against the other by hand takes weeks, and has to be redone after every commit." |
| 15-28 s | The graphical abstract animates: policy → requirements, repo → evidence, rules → LLM judge → verifier → human. | "Our Compliance-as-Code AI Auditor turns regulations into testable requirements. Fast rules check what is precise. Claude judges the rest from retrieved evidence. A verifier rejects any 'compliant' that lacks a real citation." |
| 28-42 s | Screen recording of the dashboard: score gauge, then a gap opened with file:line evidence, then the review queue. | "Every verdict links to the exact file and lines, or to a gap and a fix. When the rules and the AI disagree, a human decides, and that decision is recorded." |
| 42-52 s | Results chart (accuracy, false-compliance rate, cost per audit). | "On five hand-labelled AI applications, the hybrid mode reaches 94.5% accuracy, more than rules or the LLM alone, at about 55 cents per audit, with every citation verified." |
| 52-60 s | Logo, title, team names, "AML 2026-2027, UBB Cluj". | "Compliance you can check, cite and contest. Compliance-as-Code AI Auditor." |
