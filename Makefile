# Compliance-as-Code AI Auditor: developer shortcuts. Run `make help`.
PYTHON   ?= python3
VENV     ?= .venv
PY       := $(VENV)/bin/python
CCA      := $(VENV)/bin/ccauditor
DEMO_APP ?= app/benchmark/apps/hireright-screening
POLICIES ?= eu-ai-act acme-rai
MODE     ?= deterministic
EVAL_OUT ?= local_run
MODES    ?= deterministic
MODEL    ?= sonnet

.DEFAULT_GOAL := help
.PHONY: help install test lint audit-demo regression-demo api web web-install eval report docker clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

$(PY):
	$(PYTHON) -m venv $(VENV)

install: $(PY) ## Create .venv and install the backend (editable) + web dependencies
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e "app/backend[dev]"
	cd app/web && npm install

test: ## Backend unit tests (live LLM tests skipped) + corpus validation
	cd app/backend && ../../$(PY) -m pytest -q
	$(PY) app/benchmark/validate_corpus.py

lint: ## ESLint for the web app; ruff for the backend when available
	cd app/web && npm run lint
	@if $(PY) -m ruff --version >/dev/null 2>&1; then $(PY) -m ruff check app/backend; \
	else echo "ruff not installed (pip install ruff): skipping Python lint"; fi

audit-demo: ## Audit the demo app (MODE=deterministic|hybrid|llm) -> reports/demo.{md,json,sarif}
	@mkdir -p reports
	$(CCA) audit $(DEMO_APP) $(foreach p,$(POLICIES),-p $(p)) -m $(MODE) -f json -o reports/demo.json
	$(CCA) audit $(DEMO_APP) $(foreach p,$(POLICIES),-p $(p)) -m deterministic -f md -o reports/demo.md
	$(CCA) audit $(DEMO_APP) $(foreach p,$(POLICIES),-p $(p)) -m deterministic -f sarif -o reports/demo.sarif
	$(CCA) explain reports/demo.json AIA-REC-02 | head -30

regression-demo: ## Show `ccauditor ci` blocking a PR that removes audit logging / AI disclosure
	MODE=$(MODE) scripts/demo_regression.sh

api: ## Run the FastAPI backend on :8000 (hybrid mode needs a logged-in `claude`)
	cd app/backend && ../../$(VENV)/bin/uvicorn ccauditor.api:app --reload --port 8000

web: ## Run the Next.js dashboard on :3000 against the local API
	cd app/web && NEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_API_URL:-http://localhost:8000} npm run dev

eval: ## Benchmark evaluation (MODES=deterministic,hybrid,llm MODEL=sonnet EVAL_OUT=name)
	$(PY) app/benchmark/evaluate.py --out $(EVAL_OUT) --modes $(MODES) --model $(MODEL)

report: ## Build the LaTeX report (docs/report/report.pdf); needs latexmk
	cd docs/report && latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex

docker: ## Build and run backend + web with docker compose
	docker compose up --build

clean: ## Remove local build/test artefacts
	rm -rf reports app/backend/.pytest_cache app/web/.next
	find app -name __pycache__ -type d -prune -exec rm -rf {} +
	cd docs/report && latexmk -C >/dev/null 2>&1 || true
