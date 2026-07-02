# USD/BRL Round Numbers -- atalhos reprodutíveis do projeto.
#
# Uso: `make <alvo>` (a partir da raiz do repositório).
# Windows sem `make`: cada alvo é um one-liner; copie o comando do bloco
# correspondente. Os alvos de análise assumem as dependências instaladas
# (`make install`); o alvo `paper` assume um TeX (MiKTeX/TeX Live) no PATH.

PYTHON ?= python
PORT   ?= 4321

.DEFAULT_GOAL := help
.PHONY: help install analysis sanity event-study web-data research web paper clean

help:  ## Lista os alvos disponíveis
	@echo "Alvos disponíveis:"
	@echo "  install      instala as dependências Python (requirements.txt)"
	@echo "  analysis     roda o teste confirmatório -> results/confirmatory_results.csv"
	@echo "  sanity       roda o sanity check MT5 vs PTAX -> figures/sanity_ptax.png"
	@echo "  event-study  roda o event-study do toque -> figures/event_study.png"
	@echo "  web-data     (re)gera web/data.json a partir dos dados brutos"
	@echo "  research     analysis + sanity + event-study + web-data (tudo, menos ingestão)"
	@echo "  web          serve a experiência web em http://localhost:$(PORT)"
	@echo "  paper        compila paper/main.tex -> paper/main.pdf (precisa de TeX no PATH)"
	@echo "  clean        remove artefatos de build (LaTeX, __pycache__)"
	@echo ""
	@echo "Nota: a ingestão do MT5 (src/ingest_mt5.py) exige o terminal MetaTrader5"
	@echo "aberto e logado; o snapshot já vem versionado, então não faz parte do fluxo padrão."

install:  ## Instala as dependências Python
	$(PYTHON) -m pip install -r requirements.txt

analysis:  ## Teste confirmatório (primário + robustez)
	$(PYTHON) -m src.run_analysis

sanity:  ## Sanity check da fonte (MT5 vs PTAX oficial do BCB)
	$(PYTHON) -m src.sanity_ptax

event-study:  ## Event-study assinado do toque (redondo vs controle)
	$(PYTHON) -m src.event_study

web-data:  ## (Re)gera web/data.json
	$(PYTHON) -m src.export_web_data

research: analysis sanity event-study web-data  ## Roda todo o pipeline de análise

web:  ## Serve a experiência web (scrollytelling)
	$(PYTHON) -m http.server $(PORT) --directory web

paper:  ## Compila o paper (pdflatex -> bibtex -> pdflatex x2)
	cd paper && pdflatex -interaction=nonstopmode main.tex \
		&& bibtex main \
		&& pdflatex -interaction=nonstopmode main.tex \
		&& pdflatex -interaction=nonstopmode main.tex

clean:  ## Remove artefatos de build
	rm -rf paper/_preview
	rm -f paper/*.aux paper/*.log paper/*.bbl paper/*.blg paper/*.out \
		paper/*.toc paper/*.fls paper/*.fdb_latexmk paper/*.synctex.gz
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
