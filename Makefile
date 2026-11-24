# Developer commands for the Sales Analytics Platform.
# Run `make` or `make help` to list them.
#
# Recipe lines MUST be indented with a TAB character, not spaces.

SHELL := /bin/bash
.DEFAULT_GOAL := help

ENV_FILE := .env
COMPOSE  := docker compose --env-file $(ENV_FILE) -f infrastructure/postgres/compose.yaml
# Runs the generator inside the uv environment, with the variables from .env
GENERATOR := uv run --env-file $(ENV_FILE) python -m data_generator

# Database used by `make psql`. Override on the command line: make psql DB=crm
DB ?= postgres

# Targets that are command names, not files
.PHONY: help setup check-env up down ps logs psql reset seed stats lint format

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------
# Setup
# ---------------------------------------------------------------
setup: ## Install Python dependencies and create .env from the template if missing
	uv sync
	@if [ ! -f $(ENV_FILE) ]; then \
		cp .env.example $(ENV_FILE); \
		echo "Created $(ENV_FILE) from .env.example: set your passwords before 'make up'."; \
	fi

# Internal helper (no "##", so it is not listed by `make help`)
check-env:
	@test -f $(ENV_FILE) || { echo "Missing $(ENV_FILE). Run 'make setup' and set the passwords."; exit 1; }

# ---------------------------------------------------------------
# PostgreSQL (operational sources)
# ---------------------------------------------------------------
up: check-env ## Start PostgreSQL and wait until it is healthy
	$(COMPOSE) up -d --wait

down: check-env ## Stop and remove the container (the data volume is kept)
	$(COMPOSE) down

ps: check-env ## Show the container status
	$(COMPOSE) ps

logs: check-env ## Follow the PostgreSQL logs (Ctrl+C to exit)
	$(COMPOSE) logs -f postgres

psql: check-env ## Open psql as superuser (choose the database with DB=ecommerce|crm|erp)
	$(COMPOSE) exec postgres psql -U postgres -d $(DB)

reset: check-env ## DELETE the data volume and recreate empty databases
	@read -r -p "This deletes all source data. Type 'yes' to continue: " answer \
		&& [ "$$answer" = "yes" ] || { echo "Cancelled."; exit 1; }
	$(COMPOSE) down -v
	$(COMPOSE) up -d --wait

# ---------------------------------------------------------------
# Data generator
# ---------------------------------------------------------------
seed: up ## Rebuild the historical source data (deletes existing rows). Options: SEED=n ANCHOR=YYYY-MM-DD
	$(GENERATOR) seed $(if $(SEED),--seed $(SEED)) $(if $(ANCHOR),--anchor-date $(ANCHOR))

stats: check-env ## Show row counts per table in the source databases
	$(GENERATOR) stats

# ---------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------
lint: ## Check Python code style and common bugs (ruff)
	uv run ruff check .
	uv run ruff format --check .

format: ## Fix Python formatting and auto-fixable issues (ruff)
	uv run ruff format .
	uv run ruff check --fix .
