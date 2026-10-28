# Build the AML technical report.
#
#   make            -> report.pdf (tectonic: fetches LaTeX packages on demand, runs bibtex automatically)
#   make latexmk    -> same with a TeX Live installation (pdflatex + bibtex)
#   make todos      -> list remaining placeholders (\todo, \resultsTODO, \res, \maybefig without a file)
#   make clean
#
# Install tectonic on macOS with `brew install tectonic`.
#
# Experiments hook-ups (no edits to the .tex needed):
#   * results_tables.tex holds the main results + statistics tables (from app/benchmark/results/SUMMARY.md and
#     app/benchmark/stats_tests.py -> results/stats_tests.json);
#   * figures/results_*.pdf and figures/eda_*.pdf come from app/notebooks (01_eda / 02_results);
#   * figures/dashboard_*.png are Playwright screenshots of app/web (/reports/hireright-screening-hybrid).

MAIN = report

.PHONY: all latexmk todos clean

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex team.tex refs.bib $(wildcard sections/*.tex) results_tables.tex $(wildcard figures/*)
	tectonic --keep-logs $(MAIN).tex

latexmk:
	latexmk -pdf -interaction=nonstopmode $(MAIN).tex

todos:
	@grep -n '\\todo{\|\\resultsTODO{\|\\res{' $(MAIN).tex team.tex sections/*.tex || true
	@for f in results_v0_v1.pdf results_confusion.pdf results_cost_quality.pdf results_threshold_sweep.pdf \
	  results_per_category.pdf dashboard_overview.png dashboard_requirement.png; do \
	  ls figures/$$f >/dev/null 2>&1 || echo "missing figure: figures/$$f"; done

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot $(MAIN).loa $(MAIN).fls $(MAIN).fdb_latexmk
