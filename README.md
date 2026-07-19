# Signum — Real-Time Job Market Intelligence

Signum tracks **live** job postings and surfaces **emerging skill combinations**
before they appear in any course or blog post. It is built as a DBMS project:
the substance is a TimescaleDB event store, a **custom bitmap index**, continuous
aggregates, and honest query benchmarks — the job-market domain is the vehicle.

> All data is **real**. Sources: [Remotive](https://remotive.com) API,
> [Arbeitnow](https://www.arbeitnow.com) API (key-less), and
> [Naukri](https://www.naukri.com) via Firecrawl (India-specific, key optional).
> No synthetic data is used in the live pipeline.

## Architecture

```
React/static dashboard  ─┐
D3 skill graph          ─┤  HTTP  /api/v1/*
FastAPI backend         ─┘
   │  ingestion pipeline (real sources → spaCy skill extraction)
   ├── TimescaleDB  (hypertables: job_events, skill_cooccurrence)
   │       └── continuous aggregate: cooccurrence_30d
   └── Redis  (custom bitmap index: skill / seniority / country / company_size)
Background scheduler    ── every 6h re-runs the ingestion pipeline
```

## Run it

### With Docker (recommended)
```bash
cp .env.example .env          # add FIRECRAWL_API_KEY for India/Naukri data (optional)
make up                       # builds, starts stack, primes real data
```
This starts TimescaleDB, Redis, the API, the dashboard (`:80`), and a scheduler
that ingests real jobs every 6 hours. On Windows use `.\run.ps1 up`.

Open the dashboard at **http://localhost/** (Signals / Search / Graph / System).

### Local (no Docker)
```bash
pip install -e backend/
# start TimescaleDB + Redis (e.g. docker compose up timescaledb redis)
alembic upgrade head
python -m app.worker          # scheduler, ingests every 6h
# or one-shot:
curl -X POST http://localhost:8000/api/v1/pipeline/run -H "Authorization: Bearer $API_KEY"
uvicorn app.main:app --port 8000
```

### Makefile / run.ps1 targets
`up` · `ingest` · `signals` · `status` · `bench` · `test` · `lint` · `down`

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health + posting count |
| `/api/v1/pipeline/run` | GET/POST | Trigger real-data ingestion |
| `/api/v1/pipeline/status` | GET | Counts: postings, skills, emerging |
| `/api/v1/signals?limit=20` | GET | Emerging skill pairs (breakout score) |
| `/api/v1/search?skills=Python&seniority=senior` | GET | Multi-filter search (bitmap → B-tree fallback) |
| `/api/v1/graph?skill=Python` | GET | Co-occurrence neighbors for D3 graph |
| `/api/v1/extract` | POST | spaCy skill extraction (known + emerging) from text |
| `/api/v1/emerging` | GET | Review queue of NER-discovered skill candidates |
| `/api/v1/emerging/review` | POST | Accept (→ taxonomy) or reject a candidate |
| `/api/v1/metrics` | GET | Uptime + request counters |

## The breakout signal
```
velocity(a,b) = cooccurrence(last 30d) − cooccurrence(prior 30d)
novelty(a,b)  = 1 / (days_since_first_seen + 1)
breakout(a,b) = velocity × novelty × ln(count + 1)
```
A pair scores high only if it is **both rising and recent** — emerging, not
merely popular. See `app/api/v1/signals.py` and `docs/ADR.md` (ADR-005).

## DBMS contributions
1. Event-sourced **3NF** schema on TimescaleDB hypertables (`docs/ARCHITECTURE.md`).
2. **Custom bitmap index** in Redis for multi-filter categorical queries
   (`app/infrastructure/indexing/bitmap.py`) — benchmarked vs native B-tree.
3. **Continuous aggregate** for rolling co-occurrence (`migrations/002`).
4. Explicit **transaction boundaries** per ingestion (atomic insert + index update).

Run the honest benchmark (after real data is ingested):
```bash
python -m scripts.benchmark     # writes real numbers -> docs/benchmark_results.md
```

## Docs
- `ARCHITECTURE.md` — ER diagram, normalization, TimescaleDB, bitmap theory
- `ADR.md` — 5 architecture decision records
- `benchmark.md` — benchmark methodology; `benchmark_results.md` — real measured numbers
- `FINDING.md` — the real finding from your data (populate after first run)

## Tests
```bash
make test          # or: cd backend && python -m pytest -q
```
Covers the breakout-score math (`tests/unit/test_signals.py`) and the bitmap
index multi-filter logic (`tests/unit/test_bitmap.py`, uses fakeredis — no real
Redis needed).

## On MCP servers / plugins
This project is intentionally self-contained (FastAPI + TimescaleDB + Redis +
spaCy). **No MCP server or extra plugin is required** to build or run it — adding
one would be scope creep. The "seamless" part is handled by the `Makefile` /
`run.ps1` (one-command `up`/`ingest`/`bench`/`test`) and the Docker Compose
stack with an automatic ingestion scheduler. If you later want an LLM agent to
drive the API, the REST surface above is already agent-friendly.

