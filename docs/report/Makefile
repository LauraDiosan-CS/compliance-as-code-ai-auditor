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
#   * results_tables.tex (in this folder) replaces the placeholder main-results table if it exists;
#   * figures/<name>.pdf|png are picked up by \maybefig: mode_comparison, confusion_hybrid,
#     confusion_llm, cost_quality, per_category (see sections/experiments.tex).

MAIN = report

.PHONY: all latexmk todos clean

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex team.tex refs.bib $(wildcard sections/*.tex) $(wildcard results_tables.tex) $(wildcard figures/*)
	tectonic --keep-logs $(MAIN).tex

latexmk:
	latexmk -pdf -interaction=nonstopmode $(MAIN).tex

todos:
	@grep -n '\\todo{\|\\resultsTODO{\|\\res{' $(MAIN).tex team.tex sections/*.tex || true
	@for f in mode_comparison confusion_hybrid confusion_llm cost_quality per_category; do \
	  ls figures/$$f.pdf figures/$$f.png >/dev/null 2>&1 || echo "missing figure: figures/$$f.{pdf,png}"; done

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot $(MAIN).loa $(MAIN).fls $(MAIN).fdb_latexmk
