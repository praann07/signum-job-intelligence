# Signum — DBMS Course Report

> Fill the bracketed `[...]` fields after running the stack locally (Docker).
> Everything outside brackets is fixed and describes the system as built.

## 1. Title & One-line Summary
**Signum: a real-time job-market intelligence system with a custom bitmap index.**
It ingests *live* job postings, extracts skills with NLP, and surfaces emerging
skill combinations using a breakout signal — built on a TimescaleDB event store
with a hand-written bitmap index.

## 2. Problem & Motivation
Existing job-analytics tools show what skills are *popular*. They don't show
what skill *combinations are emerging* before they go mainstream. Signum answers
that with a quantitative signal computed over real posting history.

## 3. DBMS Contributions
1. **Event-sourced 3NF schema** on TimescaleDB hypertables (`job_events`,
   `skill_cooccurrence`). Append-only; current state = query over history.
2. **Custom bitmap index** (Redis) over `skill` / `seniority` / `country` /
   `company_size` for multi-filter categorical queries.
3. **Continuous aggregate** (`cooccurrence_30d`) for rolling co-occurrence.
4. **Atomic transaction boundaries** per ingestion (insert + index update).

## 4. Architecture
```
dashboard (static SPA + D3 graph)
        │  HTTP /api/v1/*
FastAPI backend
   ├── ingestion pipeline (Remotive + Arbeitnow + Naukri/Firecrawl) → spaCy extraction
   ├── TimescaleDB (hypertables + continuous aggregate)
   └── Redis (custom bitmap index)
scheduler: re-ingests every 6h
```

## 5. Breakout Signal (the metric)
```
velocity(a,b) = cooccurrence(last 30d) − cooccurrence(prior 30d)
novelty(a,b)  = 1 / (days_since_first_seen + 1)
breakout(a,b) = velocity × novelty × ln(count + 1)
```
A pair ranks high only if it is both *rising* and *recent*.

## 6. Benchmark Results
See `docs/benchmark_results.md` (real numbers from `make bench`). Summary:
[bitmap vs B-tree latency at 1 / 3 / 5 filters; the crossover point].

## 7. Finding (the real result)
[One genuine emerging-skill finding from your data: "Between <date> and <date>,
<X> + <Y> appeared in <N> postings, breakout <S>."]

## 8. Reproduction
```bash
cp .env.example .env
docker compose up --build      # make up
curl http://localhost:8000/api/v1/pipeline/run
# open http://localhost/  → Signals / Search / Graph / System
```

## 9. Limitations
- Bitmap index is in-memory Redis; not persisted across a flush (acceptable for
  this scale; redesign note: add AOF or rebuild from DB on boot).
- Skill extraction precision depends on the curated taxonomy; the `emerging`
  review queue closes that gap manually.
