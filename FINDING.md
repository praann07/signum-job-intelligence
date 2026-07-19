# Signum — Findings

## Data sources (ALL REAL, no synthetic generation)

| Source | Type | Coverage | Key required |
|---|---|---|---|
| Remotive API | JSON REST | Global remote roles, real tags | No |
| Arbeitnow API | JSON REST | EU/remote roles | No |
| Naukri (Firecrawl) | Scrape | **India-specific** | Optional |

Run ingestion with:

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "Authorization: Bearer $API_KEY"
```

This fetches live postings, extracts skills via NLP, writes to TimescaleDB, and
updates the bitmap index. Re-run on a cron (e.g. every 6h) to accumulate history.

## Breakout signal (the core metric)

```
velocity(a,b)  = cooccurrence(recent 30d) − cooccurrence(prior 30d)
novelty(a,b)   = 1 / (days_since_first_seen + 1)
breakout(a,b)  = velocity × novelty × ln(count + 1)
```

A pair scores high only if it is **both rising and recent** — that is
"emerging", not merely "popular". See `app/api/v1/signals.py`.

## How to produce a finding

After enough real postings are ingested (aim for 1k+ across several days so the
velocity window has signal), hit `/api/v1/signals?limit=20` and read the top
breakout pairs. Document the most interesting one here, e.g.:

> "Between <date> and <date>, the combination <X> + <Y> appeared in <N>
> postings with a breakout score of <S>, up from <prior>. This cluster is
> concentrated in <seniority/country>."

## Real finding (first live run, 2026-07-18)

After ingesting **2,330 real postings** (Remotive + Arbeitnow, live), the
top breakout skill-pairs by `velocity × novelty × ln(count+1)` are:

| Pair | Count | Recent (30d) | Velocity | Novelty | Breakout |
|---|---|---|---|---|---|
| Kubernetes + SQL | 3 | 3 | 3 | 0.20 | **0.832** |
| Python + Terraform | 3 | 3 | 3 | 0.20 | **0.832** |
| SQL + Terraform | 3 | 3 | 3 | 0.20 | **0.832** |
| Android + TypeScript | 4 | 4 | 4 | 0.04 | 0.258 |
| TypeScript + iOS | 4 | 4 | 4 | 0.04 | 0.258 |

**Finding:** The Kubernetes+SQL, Python+Terraform, and SQL+Terraform clusters
all first appeared on 2026-07-14 and hit their full volume (3 each) within the
last 7 days — a clean `velocity = +3` with maximum novelty. This points to a
fresh "infra-as-code + data" hiring cluster (Terraform paired with both a
language and a data skill) that is new in this window, not merely popular.

Caveat: at 2,330 postings the absolute counts are small, so these are
*early-warning* signals, not mature trends. Re-run every 6h to let the velocity
window accumulate. Full machine-readable output: `/api/v1/signals`.

> NOTE: The earlier synthetic "Docker + Python dominates" finding has been
> removed because it was generated from fake data.
