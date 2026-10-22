# Product commands for app/ (server + client). Run from the repo root via `make <target>`,
# or here with `make <target>`. Client steps are skipped until app/client/node_modules exists.

.DEFAULT_GOAL := help
.PHONY: help server client dev format check test docs verify

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

server: ## Run the server on :8000 with reload
	cd server && uv run uvicorn system1.main:app --reload --port 8000

client: ## Run the client dev server
	cd client && bun run dev

dev: ## Run server and client together
	bunx concurrently -k -n server,client "$(MAKE) server" "$(MAKE) client"

format: ## Format the server (ruff) and the client (Prettier)
	cd server && uv run ruff format . && uv run ruff check --fix .
	@if [ -d client/node_modules ]; then cd client && bunx prettier --write .; else echo "skip: client not installed"; fi

check: ## Lint and typecheck both sides
	cd server && uv run ruff check . && uv run ruff format --check .
	@if [ -d client/node_modules ]; then cd client && bun run typecheck; else echo "skip: client not installed"; fi

test: ## Run the server tests
	cd server && uv run pytest -q

docs: ## Regenerate the OpenAPI schema and the client's types
	cd server && uv run python -m system1.openapi_dump ../client/src/lib/api/openapi.json
	@if [ -d client/node_modules ]; then cd client && bunx openapi-typescript src/lib/api/openapi.json -o src/lib/api/schema.d.ts; else echo "skip: client not installed"; fi

verify: check test ## Run check, test and the client build
	@if [ -d client/node_modules ]; then cd client && bun run build; else echo "skip: client not installed"; fi
