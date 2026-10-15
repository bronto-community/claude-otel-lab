PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python

.PHONY: help setup demo postmortem chaos server alert test clean

help:  ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'

$(PY):
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -r requirements.txt

.env:
	cp .env.example .env
	@echo "Created .env: add your ANTHROPIC_API_KEY (and BRONTO_API_KEY or OTEL_* settings), then run make demo."
	@false

setup: $(PY) .env  ## Create the virtualenv and .env

demo: setup  ## Fire one alert: triage only (a few cents)
	@scripts/demo.sh

postmortem: setup  ## Fire one alert, then write a postmortem with Managed Agents (~$0.25, capped)
	@scripts/demo.sh --postmortem

chaos: setup  ## Fire one alert while the metrics backend times out
	@scripts/demo.sh --chaos

server: setup  ## Run the copilot in the foreground on :8000
	$(PY) -m uvicorn oncall.app:app --port 8000

alert: setup  ## Fire an alert at a running copilot
	$(PY) -m oncall.fire_alert

test: $(PY)  ## Run the offline tests (no API key needed)
	$(VENV)/bin/pip install -q pytest httpx
	$(VENV)/bin/pytest -q

clean:  ## Remove the virtualenv and local state
	rm -rf $(VENV) .lab-state.json postmortems copilot.log
