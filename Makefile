.PHONY: up down build test lint fmt migrate ingest shell

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check .

fmt:
	cd backend && ruff format .

migrate:
	docker exec signum-backend-1 alembic upgrade head

ingest:
	@API_KEY=$$(grep -E '^API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2); \
	if [ -z "$$API_KEY" ]; then \
		echo "Error: API_KEY not found in .env"; exit 1; \
	fi; \
	curl -s -X POST http://localhost:8000/api/v1/pipeline/run \
		-H "Authorization: Bearer $$API_KEY" | python -m json.tool

shell:
	docker compose exec backend sh
