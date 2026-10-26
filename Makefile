# Common commands for system1. Run `make` or `make help` to list them.
# Secrets are read from .env (copy .env.example to create it).
#
# Uses ./.venv by default. To use a different env (e.g. the README's unsloth_env):
#   make install VENV=unsloth_env

VENV       ?= .venv
PY_VERSION ?= 3.12
PYTHON     := $(VENV)/bin/python
MODAL      := $(VENV)/bin/modal

# Optional row limit for smoke tests: make eval-jev LIMIT=50
LIMIT ?=
LIMIT_ARG := $(if $(LIMIT),--limit $(LIMIT),)

# Dataset the training and eval targets use (decision rows from data/banking/to_decision_parquet.py).
# Override with DATA=path, or DATA= to fall back to LocalLLaMA/typed-decisions.
DATA     ?= data/banking/banking77_decisions.parquet
DATA_ARG := $(if $(DATA),--data $(DATA),)
EPOCHS   ?= 1

# Load .env into each recipe's shell. The shell parses the file, so keys never pass
# through make and never appear in echoed commands.
LOAD_ENV := set -a; [ -f .env ] && . ./.env; set +a;

.DEFAULT_GOAL := help
.PHONY: help env venv install test dev format check docs verify modal-setup check-env jev-check train eval-laya eval-lora eval-jev eval-all modal-deploy grid tickets-check blind readback dataset dataset-provisional generate clean

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Smoke-test any eval with LIMIT, e.g. make eval-jev LIMIT=50"

# --- Setup -----------------------------------------------------------------

env: ## Create .env from .env.example (never overwrites an existing .env)
	@if [ -f .env ]; then echo ".env already exists; leaving it alone."; else cp .env.example .env && echo "Created .env. Add your keys."; fi

venv: ## Create the virtualenv with uv, if it doesn't exist yet
	@[ -d $(VENV) ] || uv venv $(VENV) --python $(PY_VERSION)

install: venv ## Install local dependencies (modal, eval_jev.py deps, data pipeline and tests)
	uv pip install --python $(PYTHON) modal requests datasets pytest pandas pyarrow matplotlib

test: ## Run the phase 1 tests and the product server tests
	$(PYTHON) -m pytest -q tests
	$(MAKE) -C app test

# --- Product (app/) ---------------------------------------------------------

dev: ## Run the product server and client together
	$(MAKE) -C app dev

format: ## Format the product code (ruff, Prettier)
	$(MAKE) -C app format

check: ## Lint and typecheck the product code
	$(MAKE) -C app check

docs: ## Regenerate the OpenAPI schema and the client's types
	$(MAKE) -C app docs

verify: ## Run check, test and the client build for the product
	$(MAKE) -C app verify

modal-setup: ## Authenticate the Modal CLI (opens a browser)
	$(MODAL) setup

check-env: ## Check that required secrets are set (prints names, never values)
	@$(LOAD_ENV) missing=0; \
	for v in TYPESAFE_API_KEY TYPESAFE_BASE_URL JEV_MODEL; do \
		eval "val=\$${$$v:-}"; \
		if [ -z "$$val" ]; then echo "missing: $$v"; missing=1; else echo "ok:      $$v"; fi; \
	done; \
	exit $$missing

jev-check: check-env ## Verify the Jev key by listing models (no decisions are made)
	@$(LOAD_ENV) curl -sS --fail-with-body \
		-H "Authorization: Bearer $$TYPESAFE_API_KEY" \
		"$$TYPESAFE_BASE_URL/v1/models"; echo

# --- Training and evaluation ------------------------------------------------
# These run on $(DATA), Banking77 by default.

train: ## Train the Laya LoRA on Modal (L4) and download it to ./lora
	$(MODAL) run train.py $(DATA_ARG) --epochs $(EPOCHS)

eval-laya: ## Evaluate untrained Laya on the test split (Modal) -> results/laya_*
	$(MODAL) run eval_laya.py $(DATA_ARG) $(LIMIT_ARG)

eval-lora: ## Evaluate the trained LoRA in ./lora on the test split (Modal) -> results/laya_lora_*
	@[ -f lora/trainable.pt ] || { echo "lora/trainable.pt not found. Run 'make train' first."; exit 1; }
	$(MODAL) run eval_lora.py $(DATA_ARG) $(LIMIT_ARG)

eval-jev: check-env ## Evaluate Jev (hosted API, pinned to JEV_MODEL) on the test split -> results/jev_*
	@$(LOAD_ENV) $(PYTHON) eval_jev.py --model "$$JEV_MODEL" $(DATA_ARG) $(LIMIT_ARG)

eval-all: eval-laya eval-lora eval-jev ## Run all three evals

modal-deploy: ## Deploy pipeline.py to Modal so the server's TRAINER=modal can call it
	$(MODAL) deploy pipeline.py

# --- Phase 1 dataset --------------------------------------------------------

grid: ## Build the seeded facts grid -> data/raw/facts.jsonl
	$(PYTHON) facts_grid.py --n 550 --seed 20261020 --out data/raw/facts.jsonl

tickets-check: ## Validate data/raw/tickets.jsonl against the facts grid
	$(PYTHON) tickets.py validate

blind: ## Write the blind file for the read-back agent (ONLY_FAILED=1 for the retry round)
	$(PYTHON) readback.py blind $(if $(ONLY_FAILED),--only-failed data/readback/report.json,)

readback: ## Compare the agent's extraction with intended facts -> data/readback/report.json (EXTRA=retry file)
	$(PYTHON) readback.py compare data/readback/extracted.jsonl $(EXTRA)

dataset: ## Build data/build/triage.parquet from read-back-verified tickets (freezes splits)
	$(PYTHON) build_dataset.py

dataset-provisional: ## Build data/build/triage_provisional.parquet without the read-back filter (not for results)
	$(PYTHON) build_dataset.py --provisional

# --- Housekeeping -----------------------------------------------------------

generate: ## Generate new labelled rows with NeMo Data Designer: make generate SOURCE=data/banking/banking_upload.csv PER_LABEL=20 OUT=data/banking/banking_new.csv
	@$(LOAD_ENV) $(PYTHON) generate_data.py --source $(SOURCE) --per-label $(or $(PER_LABEL),10) $(if $(OUT),--out $(OUT),--dry-run)

clean: ## Remove Python caches (leaves ./lora, data and results alone)
	find . -path ./$(VENV) -prune -o -type d -name __pycache__ -exec rm -rf {} +
