# Contributing

Team: Bâlc Felicia, Drăghici Eduard, Gog Raluca. These rules apply to the application (`app/`) and to the
documentation and LaTeX report (`docs/`).

## Workflow per project stage

The project is delivered in stages. **In every stage, each team member opens at least 2 pull requests**,
and the PRs must cover both:

- the **application** (`app/backend`, `app/web`, `app/benchmark`, `app/notebooks`, CI), and
- the **report** (`docs/report`, `docs/design`).

That makes at least 6 PRs per stage for the team. Small, focused PRs are better than one large PR at the
end of a stage.

1. **Open or claim an issue** for the work. Use the stage label (e.g. `stage-2`) and the area label
   (`app`, `report`).
2. **Branch from an up-to-date `main`.** Name the branch `<type>/<stage>-<short-topic>`:

   ```bash
   git switch main && git pull
   git switch -c feat/s2-gdpr-retention-rules      # or docs/s2-related-work, fix/s3-sarif-paths
   ```

3. **Commit in small steps** with [Conventional Commits](#commit-messages).
4. **Run the checks locally** before pushing:

   ```bash
   make test        # pytest + benchmark corpus validation
   make lint        # web ESLint (+ ruff if installed)
   make report      # if you touched docs/report
   ```

5. **Open a PR to `main`.** Fill in the template (what changed, why, how it was tested, stage, linked
   issue) and request a review from at least one other team member.
6. **CI must be green.** `tests` covers pytest on Python 3.12/3.13 and the web lint/build. `compliance`
   is our own auditor: it fails when a PR introduces a high or critical compliance regression in the
   audited target. Its sticky PR comment and the SARIF in *Security > Code scanning* (when available)
   show which requirement regressed and the lost evidence.
7. **Merge with squash** after approval. The squash title must also be a Conventional Commit. Delete the
   branch afterwards.

Never push directly to `main`. Enable branch protection with *Require a pull request* and the required
status checks `tests` and `compliance / deterministic audit (blocking)`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <imperative summary, at most 72 chars>

<optional body: what and why>

<optional footer: Refs #12, BREAKING CHANGE: ...>
```

| Type | Use for |
|---|---|
| `feat` | new functionality (agent, rule type, endpoint, dashboard page) |
| `fix` | bug fix |
| `docs` | README, design docs, **LaTeX report** |
| `test` | tests only |
| `refactor` | code change without behaviour change |
| `perf` | performance |
| `ci` | GitHub Actions, Docker, Vercel config |
| `build` | dependencies, packaging |
| `chore` | maintenance |
| `data` | policy corpora, requirements YAML, benchmark apps and ground truth |
| `exp` | experiments, evaluation runs, notebooks |

Scopes we use: `backend`, `agents`, `rules`, `api`, `cli`, `web`, `benchmark`, `notebooks`, `report`,
`policies`, `ci`.

Examples:

```
feat(rules): support `absent` checks for IaC retention settings
fix(api): fall back to GitHub tarball when git is unavailable
docs(report): add evaluation methodology section
data(benchmark): label GDPR requirements for credit-lens
exp(benchmark): hybrid vs deterministic run with haiku
ci: post sticky PR comment with compliance summary
```

## Code conventions

- **Python:** 3.11 or newer with type hints. Keep the shared contracts in `ccauditor/models.py` stable;
  if you change a field, update every user and the web types. New behaviour needs a pytest test that runs
  offline: use `FakeBackend` for LLM agents and mark real CLI calls with `@pytest.mark.live`.
- **Policies and requirements:** follow the formats in `README.md`. Run
  `python app/benchmark/validate_corpus.py` after every change.
- **Benchmark ground truth:** label from the requirement statement, never from the rule engine output.
  Explain non-obvious labels in `notes`.
- **Web:** TypeScript, ESLint clean, and `npm run build` must pass.
- **Report:** one `\section` per file under `docs/report/sections/`. Put citations in `refs.bib`. Do not
  commit build artefacts (`*.aux`, `*.log`, ...).
- Never commit secrets. `CLAUDE_CODE_OAUTH_TOKEN` belongs in repository secrets, and `.env*` files are
  ignored.
