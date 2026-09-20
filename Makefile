.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend
# Production host details live in the gitignored .env.production (DEPLOY_HOST=deploy@1.2.3.4).
-include .env.production
export

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

seed: ## Reference data + coach login + the real 2026/27 season (idempotent)
	cd $(BACKEND) && uv run python -m scripts.seed

seed-demo: ## Reset the dev DB and load the fictional demo season (the test oracle)
	cd $(BACKEND) && uv run python -m scripts.seed --reset --demo

test: ## Run the backend test suite
	# .env.production is exported above for deploys; keep its secrets out of the tests
	cd $(BACKEND) && env -u ABGFC_COACH_PASSWORD -u ABGFC_SECRET_KEY uv run pytest -q

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

# --- production (DigitalOcean droplet) --------------------------------------------------

SSH_PUBLIC_KEY ?= ~/.ssh/abgfc_deploy.pub

droplet: ## One-off: create the $6 London droplet from deploy/cloud-init.yaml
	@test -n "$(SSH_KEY_ID)" || (echo "SSH_KEY_ID=<id from 'doctl compute ssh-key list'> required"; exit 1)
	sed "s|__SSH_PUBLIC_KEY__|$$(cat $(SSH_PUBLIC_KEY))|" deploy/cloud-init.yaml > /tmp/abgfc-cloud-init.yaml
	doctl compute droplet create abgfc --region lon1 --size s-1vcpu-1gb --image ubuntu-24-04-x64 \
		--ssh-keys $(SSH_KEY_ID) --user-data-file /tmp/abgfc-cloud-init.yaml --tag-name abgfc \
		--wait --format ID,Name,PublicIPv4,Status

deploy: ## Update the production stack from main (pulls images built by CI)
	@test -n "$(DEPLOY_HOST)" || (echo "DEPLOY_HOST=deploy@<ip> required in .env.production"; exit 1)
	ssh $(DEPLOY_HOST) 'set -e; cd /opt/abgfc && git pull --ff-only \
		&& docker compose -f docker-compose.prod.yml pull -q \
		&& docker compose -f docker-compose.prod.yml up -d --remove-orphans \
		&& docker image prune -f >/dev/null \
		&& (crontab -l 2>/dev/null | grep -q deploy/backup.sh || (crontab -l 2>/dev/null; echo "0 2 * * * /opt/abgfc/deploy/backup.sh >> /data/backups/backup.log 2>&1") | crontab -) \
		&& docker compose -f docker-compose.prod.yml ps'

backup: ## Take a fresh consistent backup on the droplet and copy it to data/backups/
	@test -n "$(DEPLOY_HOST)" || (echo "DEPLOY_HOST required in .env.production"; exit 1)
	@mkdir -p data/backups
	@ssh $(DEPLOY_HOST) '/opt/abgfc/deploy/backup.sh'
	@f=$$(ssh $(DEPLOY_HOST) 'ls -t /data/backups/abgfc-*.db | head -1'); \
		scp -q $(DEPLOY_HOST):$$f data/backups/ && echo "saved data/backups/$$(basename $$f)"

restore: ## Restore a backup to production: make restore FILE=data/backups/abgfc-....db
	@test -n "$(FILE)" || (echo "FILE=data/backups/abgfc-....db required"; exit 1)
	@test -f "$(FILE)" || (echo "$(FILE) not found"; exit 1)
	@echo "This replaces the production database with $(FILE). Ctrl-C within 5s to abort."; sleep 5
	@scp -q "$(FILE)" $(DEPLOY_HOST):/tmp/restore.db
	@ssh $(DEPLOY_HOST) '/opt/abgfc/deploy/restore.sh /tmp/restore.db && rm -f /tmp/restore.db'

prod-logs: ## Tail production logs
	ssh $(DEPLOY_HOST) 'cd /opt/abgfc && docker compose -f docker-compose.prod.yml logs -f --tail 100'

prod-shell: ## SSH to the droplet
	ssh $(DEPLOY_HOST)

.PHONY: help install dev backend frontend migrate migration seed seed-demo test lint format api-client check-api up droplet deploy prod-logs prod-shell backup restore
