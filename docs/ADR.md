# Architecture Decision Records (ADR)

## ADR-001: Event-sourced append-only schema
**Decision:** Job postings are never updated, only inserted. Current market state
is always a query over history.
**Rejected:** Mutable `jobs` table with UPDATE on refresh.
**Why:** Postings are immutable facts. Append-only gives an audit trail and makes
time-windowed signal computation trivial. Update-in-place loses history.

## ADR-002: TimescaleDB over raw Postgres / InfluxDB
**Decision:** TimescaleDB (Postgres extension).
**Rejected:** InfluxDB (no relational joins for skill co-occurrence), raw Postgres
(no native time partitioning / continuous aggregates).
**Why:** We need time-series performance *and* relational joins across
`job_skills`. TimescaleDB gives both.

## ADR-003: Custom bitmap index over native B-tree for multi-filter categorical queries
**Decision:** Implement a bitmap index in Redis for `skill`/`seniority`/`country`/
`company_size`.
**Rejected:** Relying solely on B-tree indexes.
**Why:** Dashboard queries AND 3–5 categorical filters. Bitmap AND is
`O(rows/64)` flat; B-tree intersection cost scales per filter. Benchmark shows
the crossover at ~3 filters. Kept native B-tree as a fallback when Redis is down.

## ADR-004: Two-stage skill extraction
**Decision:** Stage 1 exact/alias match vs taxonomy (precision); Stage 2 spaCy
noun-chunk NER to surface *unknown* skills into `emerging_candidates`.
**Rejected:** Hardcoded regex list only (cannot discover new skills), or NER-only
(no precision).
**Why:** We want both high-precision known-skill counts AND discovery of emerging
skills — the core differentiator vs existing dashboards.

## ADR-005: Breakout = velocity × novelty × log(count)
**Decision:** `breakout = (recent − prior) × 1/(age+1) × ln(total+1)`.
**Rejected:** Raw frequency (rewards only old popular pairs), velocity-only
(rewards noise), novelty-only (rewards one-off flukes).
**Why:** Velocity captures *acceleration*, novelty discounts long-established
pairs, log(count) dampens sheer volume. A pair must be both rising and recent to
score high — that is "emerging", not "popular".
