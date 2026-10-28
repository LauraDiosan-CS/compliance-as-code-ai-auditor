#!/usr/bin/env bash
# Demo of compliance-as-code in CI: a "move fast" pull request silently removes compliance controls
# from the hireright-screening benchmark app and `ccauditor ci` blocks it.
#
#   scripts/demo_regression.sh                 # deterministic (rules only, no LLM)
#   MODE=hybrid scripts/demo_regression.sh     # also uses the Claude Code CLI (must be logged in)
#
# Steps: copy the app into a throw-away git repo -> audit `main` (baseline) -> commit a PR that
#   1. deletes the DecisionJournal audit-logging calls and cuts the decision-journal retention from
#      400 to 30 days "to save S3 Object Lock costs"      (EU AI Act Art. 12/19/26(6), ACME POL-3)
#   2. deletes the "AI-suggested ranking" disclosure in the recruiter UI (ACME POL-1)
# Note: the journal.record(...) calls themselves are a deliberate regex false negative of the
# deterministic engine (see app/benchmark/README.md); hybrid mode also judges them with the LLM.
# -> `ccauditor ci --baseline ... --base-ref main` must exit 1 with REGRESSION lines.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${APP:-$ROOT/app/benchmark/apps/hireright-screening}"
MODE="${MODE:-deterministic}"
FAIL_ON="${FAIL_ON:-high}"
POLICIES="${POLICIES:-eu-ai-act acme-rai}"
if [[ -x "$ROOT/.venv/bin/ccauditor" ]]; then CCA="$ROOT/.venv/bin/ccauditor"; PY="$ROOT/.venv/bin/python";
else CCA="$(command -v ccauditor)"; PY="$(command -v python3)"; fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ccauditor-demo.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/repo"; OUT="$WORK/reports"; mkdir -p "$OUT"
POLICY_ARGS=(); for p in $POLICIES; do POLICY_ARGS+=(-p "$p"); done
git_() { git -C "$REPO" -c user.name=demo -c user.email=demo@example.com "$@"; }
banner() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

banner "1. Baseline: copy $(basename "$APP") into a fresh git repo ($REPO)"
cp -R "$APP" "$REPO"
git_ init -q -b main && git_ add -A && git_ commit -qm "baseline"
"$CCA" audit "$REPO" "${POLICY_ARGS[@]}" -m "$MODE" -f json -o "$OUT/baseline.json"

banner "2. Pull request: remove audit logging + log retention and the AI disclosure"
git_ checkout -qb feature/faster-ranking
"$PY" - "$REPO" <<'PYEOF'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
api = root / "src/hireright/api.py"
# 1) drop every (possibly multi-line) journal.record(...) audit-log call
out, depth, n_log = [], 0, 0
for line in api.read_text().splitlines(keepends=True):
    if depth == 0 and line.lstrip().startswith("journal.record("):
        n_log += 1
        depth = line.count("(") - line.count(")")
        continue
    if depth > 0:
        depth += line.count("(") - line.count(")")
        continue
    out.append(line)
api.write_text("".join(out))
ret = root / "config/retention.yaml"
ret_src, n_ret = re.subn(r"(decision_journal:[^\n]*\n\s*retention_days:\s*)\d+", r"\g<1>30", ret.read_text())
ret.write_text(ret_src)
ui = root / "web/src/components/CandidateRanking.tsx"
ui_src, n_notice = re.subn(r'\s*<div className="notice" role="note">.*?</div>', "", ui.read_text(), flags=re.S)
ui.write_text(ui_src)
print(f"removed {n_log} audit-log call(s) and {n_notice} AI disclosure notice(s); shortened {n_ret} log retention(s) to 30 days")
PYEOF
git_ add -A && git_ commit -qm "chore: drop decision journal writes, shorten retention, simplify UI"
git_ --no-pager diff --stat main

banner "3. CI gate: ccauditor ci --baseline baseline.json --base-ref main --fail-on $FAIL_ON"
set +e
"$CCA" ci "$REPO" --baseline "$OUT/baseline.json" --base-ref main --fail-on "$FAIL_ON" -m "$MODE" \
  --out "$OUT/current.json" --sarif "$OUT/current.sarif" --markdown-summary "$OUT/summary.md"
CODE=$?
set -e

banner "4. PR comment preview ($OUT/summary.md)"
cat "$OUT/summary.md"

if [[ $CODE -eq 1 ]]; then
  banner "OK: ccauditor ci exited 1, the pull request would be blocked"
  exit 0
fi
banner "UNEXPECTED: ccauditor ci exited $CODE (expected 1)"
exit 1
