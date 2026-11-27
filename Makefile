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

# Airbyte, installed by abctl (version: `abctl version`, see PROJECT_CONTEXT.md).
# Chart versions: https://airbytehq.github.io/charts (chart X.Y.Z = Airbyte X.Y.Z)
AIRBYTE_CHART_VERSION := 2.6.0
AIRBYTE_PORT          := 8000
# Docker container that runs the kind cluster created by abctl
AIRBYTE_NODE          := airbyte-abctl-control-plane
# Host name of PostgreSQL as seen from Airbyte (used in the source configuration)
AIRBYTE_PG_HOST       := sources-postgres

# Targets that are command names, not files
.PHONY: help setup check-env up down ps logs psql reset seed simulate stats test lint format \
	airbyte-up airbyte-down airbyte-credentials airbyte-upgrade airbyte-network

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

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
	@$(MAKE) --no-print-directory airbyte-network

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

simulate: up ## Add one run of new source activity (real timestamps). Options: ORDERS=n
	$(GENERATOR) simulate $(if $(ORDERS),--orders $(ORDERS))

stats: check-env ## Show row counts per table in the source databases
	$(GENERATOR) stats

# ---------------------------------------------------------------
# Airbyte (local, installed by abctl in a kind cluster)
# ---------------------------------------------------------------
airbyte-up: up ## Install Airbyte on the first run, start it afterwards (http://localhost:8000)
	@if docker container inspect $(AIRBYTE_NODE) >/dev/null 2>&1; then \
		docker start $(AIRBYTE_NODE) >/dev/null; \
		echo "Airbyte started. The web UI takes 1-3 minutes to answer at http://localhost:$(AIRBYTE_PORT)"; \
	else \
		abctl local install --chart-version $(AIRBYTE_CHART_VERSION) --port $(AIRBYTE_PORT) --no-browser; \
	fi
	@$(MAKE) --no-print-directory airbyte-network

airbyte-down: ## Stop Airbyte (configuration and sync history are kept)
	docker stop $(AIRBYTE_NODE)

airbyte-credentials: ## Show the Airbyte login (email, password) and API client id and secret
	abctl local credentials

airbyte-upgrade: ## Install or upgrade to AIRBYTE_CHART_VERSION (configuration is kept)
	abctl local install --chart-version $(AIRBYTE_CHART_VERSION) --port $(AIRBYTE_PORT) --no-browser

# Internal helper: lets Airbyte reach PostgreSQL. Airbyte runs inside the kind
# container, where "localhost" is that container, not this machine. The
# PostgreSQL container joins kind's Docker network under the name in
# AIRBYTE_PG_HOST. Its published port stays bound to 127.0.0.1.
# Does nothing if Airbyte is not installed (no kind network) or PostgreSQL is down.
airbyte-network:
	@pg=$$($(COMPOSE) ps -q postgres 2>/dev/null); \
	if [ -n "$$pg" ] && docker network inspect kind >/dev/null 2>&1; then \
		if docker network inspect kind --format '{{range .Containers}}{{.Name}} {{end}}' \
			| grep -qw "$$(docker inspect --format '{{.Name}}' $$pg | tr -d /)"; then \
			: already connected; \
		else \
			docker network connect --alias $(AIRBYTE_PG_HOST) kind $$pg \
				&& echo "PostgreSQL reachable from Airbyte as $(AIRBYTE_PG_HOST):5432"; \
		fi; \
	fi

# ---------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------
test: ## Run the automated tests (no database needed)
	uv run pytest

lint: ## Check Python code style and common bugs (ruff)
	uv run ruff check .
	uv run ruff format --check .

format: ## Fix Python formatting and auto-fixable issues (ruff)
	uv run ruff format .
	uv run ruff check --fix .
