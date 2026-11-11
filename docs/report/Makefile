# Build the AML technical report.
#
#   make            -> report.pdf (tectonic: fetches LaTeX packages on demand, runs bibtex automatically)
#   make latexmk    -> same with a TeX Live installation (pdflatex + bibtex)
#   make todos      -> list remaining placeholders (\todo, \plannedTODO, \resultsTODO, \res, missing figures)
#   make clean
#
# Install tectonic on macOS with `brew install tectonic`.
#
# Seminar 4 version (pipeline + first v0 results). Data hook-ups:
#   * results_tables.tex holds the v0 results + statistics tables (from the v0_baseline rows of
#     app/benchmark/results/SUMMARY.md and `app/benchmark/stats_tests.py --run v0_baseline` -> results/stats_tests_v0.json);
#   * figures/results_v0_*.pdf come from app/benchmark/plot_v0.py; figures/eda_*.pdf from app/notebooks/01_eda.

MAIN = report

.PHONY: all latexmk todos clean

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex team.tex refs.bib $(wildcard sections/*.tex) results_tables.tex $(wildcard figures/*)
	tectonic --keep-logs $(MAIN).tex

latexmk:
	latexmk -pdf -interaction=nonstopmode $(MAIN).tex

todos:
	@grep -n '\\todo{\|\\plannedTODO{\|\\resultsTODO{\|\\res{' team.tex sections/*.tex || true
	@for f in results_v0_modes.pdf results_v0_confusion.pdf results_v0_per_category.pdf results_v0_cost.pdf \
	  eda_clauses.pdf eda_requirements.pdf eda_benchmark_files.pdf eda_labels.pdf eda_signals.pdf; do \
	  ls figures/$$f >/dev/null 2>&1 || echo "missing figure: figures/$$f"; done

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot $(MAIN).loa $(MAIN).fls $(MAIN).fdb_latexmk
