# Signum — one-command workflow
# Usage:  make up        # build + start everything (DB, Redis, API, dashboard, scheduler)
#         make ingest    # trigger a real-data ingestion run
#         make signals   # show emerging skill pairs
#         make bench     # run the bitmap-vs-btree benchmark
#         make test      # run backend tests
#         make lint      # ruff
#         make down      # stop everything

COMPOSE = docker compose
API = http://localhost:8000/api/v1
KEY = dev-api-key-change-in-production

up:
	$(COMPOSE) up --build -d
	@echo "Waiting for API..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -s $(API)/health >/dev/null 2>&1 && break; \
		sleep 2; \
	done
	@echo "Priming with real data (Remotive + Arbeitnow)..."
	curl -s -X POST $(API)/pipeline/run -H "Authorization: Bearer $(KEY)" | head -c 200; echo

ingest:
	curl -s -X POST $(API)/pipeline/run -H "Authorization: Bearer $(KEY)" | python -m json.tool

signals:
	curl -s "$(API)/signals?limit=20" | python -m json.tool

status:
	curl -s $(API)/pipeline/status | python -m json.tool

bench:
	cd backend && python -m scripts.benchmark

test:
	cd backend && python -m pytest -q

lint:
	cd backend && ruff check .

down:
	$(COMPOSE) down
