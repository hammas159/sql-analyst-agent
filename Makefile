.DEFAULT_GOAL := help
SHELL := /bin/sh

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Start Postgres
	docker compose up -d --wait

down:  ## Stop it (keeps data)
	docker compose down

clean:  ## Stop and DELETE the database
	docker compose down -v

install:  ## Create .venv, install everything, and create .env
	uv sync --all-groups
	@test -f .env || cp .env.example .env

seed:  ## Generate and load the demo dataset
	uv run python scripts/seed.py

status:  ## Check dependencies, and prove the agent role cannot write
	uv run sqlanalyst status

schema:  ## Print the schema exactly as the model sees it
	uv run sqlanalyst schema

ask:  ## Ask a question:  make ask Q="total revenue by region"
	uv run sqlanalyst ask "$(Q)" --trace

api:  ## Run the API on :8001
	uv run uvicorn sqlanalyst.api.main:app --reload --port 8001

ui:  ## Run the Streamlit UI on :8502
	uv run streamlit run ui/app.py --server.port 8502

eval:  ## Run the question set and write RESULTS.md
	uv run sqlanalyst eval

test:  ## Run tests
	uv run pytest -q

lint:  ## Lint
	uv run ruff check src tests scripts
	uv run ruff format --check src tests

fmt:  ## Auto-format
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

.PHONY: help up down clean install seed status schema ask api ui eval test lint fmt
