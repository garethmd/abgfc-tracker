.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install

dev: ## Run backend (:8000) and frontend (:3000) together with hot reload
	@trap 'kill 0' INT TERM; \
	(cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd $(FRONTEND) && npm run dev) & \
	wait

backend: ## Run only the API with hot reload
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000

frontend: ## Run only the Next.js dev server
	cd $(FRONTEND) && npm run dev

migrate: ## Apply Alembic migrations
	cd $(BACKEND) && uv run alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add foo"
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

seed: ## Reference data + coach login (idempotent)
	cd $(BACKEND) && uv run python -m scripts.seed

seed-demo: ## Reset the dev DB and load the demo 2026/27 season
	cd $(BACKEND) && uv run python -m scripts.seed --reset --demo

test: ## Run the backend test suite
	cd $(BACKEND) && uv run pytest -q

lint: ## Lint + typecheck everything
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npx next typegen >/dev/null && npm run lint && npm run typecheck

format: ## Format backend code
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .

api-client: ## Regenerate frontend/lib/api/schema.d.ts from the backend's OpenAPI schema
	cd $(BACKEND) && uv run python -m scripts.export_openapi ../$(FRONTEND)/lib/api/openapi.json
	cd $(FRONTEND) && npm run api:generate

check-api: api-client ## Fail if the committed API client is out of date with the backend
	@git diff --quiet -- $(FRONTEND)/lib/api/ || (echo "API client out of date: run 'make api-client' and commit"; git --no-pager diff --stat -- $(FRONTEND)/lib/api/; exit 1)

up: ## docker compose up --build
	docker compose up --build

.PHONY: help install dev backend frontend migrate migration seed seed-demo test lint format api-client check-api up
