.PHONY: dev dev-backend dev-frontend migrate test sync-data lint format

# Start all services
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Start backend dependencies only (DB + Redis) and run FastAPI dev server
dev-backend:
	docker compose up -d db redis
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

# Start frontend dev server
dev-frontend:
	cd frontend/apps/admin && pnpm exec next dev --turbopack --hostname 0.0.0.0 --port 5001

# Run database migrations
migrate:
	cd backend && uv run alembic upgrade head

# Generate a new migration
makemigration:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

# Run tests
test:
	cd backend && uv run pytest tests/ -v

# Sync market data manually
sync-data:
	curl -X POST http://localhost:5000/api/v1/market/sync

# Lint all code
lint:
	cd backend && uv run ruff check . && uv run mypy app/
	cd frontend && pnpm lint

# Format all code
format:
	cd backend && uv run ruff format .
	cd frontend && pnpm format

# Stop all services
down:
	docker compose down

# Reset database
reset-db:
	docker compose down -v
	docker compose up -d db redis
	sleep 3
	cd backend && uv run alembic upgrade head

# Install backend dependencies
install-backend:
	cd backend && uv sync

# Install frontend dependencies
install-frontend:
	cd frontend && pnpm install
