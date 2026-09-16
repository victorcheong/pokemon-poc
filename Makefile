.PHONY: up up-win down logs test lint backend frontend

# Windows Docker Desktop CLI, for WSL shells that cannot yet reach /var/run/docker.sock.
DOCKER_EXE := /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe

up:            ## Build and run the whole stack (http://localhost:8080)
	docker compose up --build

up-win:        ## Same as `up`, but via the Windows docker.exe (WSL workaround)
	CLAUDE_DIR=$(HOME)/.claude CLAUDE_JSON=$(HOME)/.claude.json WSLENV=CLAUDE_DIR/p:CLAUDE_JSON/p \
		$(DOCKER_EXE) compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:          ## Run backend tests locally with uv
	cd backend && uv run --extra dev pytest -q

lint:
	cd backend && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .

backend:       ## Run API locally with hot reload on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:      ## Run Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm install && npm run dev
