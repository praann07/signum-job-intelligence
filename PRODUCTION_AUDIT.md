# Signum — Final Production Readiness Audit Report

**Date:** 2026-07-19
**Auditor:** Principal Engineer (Final Sign-off Review)
**Scope:** Complete end-to-end audit of Signum backend + deployment + documentation
**Method:** Source code review, lint, test execution, schema verification, security review, deployment verification

---

## 1. EXECUTIVE SUMMARY

The previous "production-ready" declaration was **FALSE**. The codebase had a blocking import error that prevented the application from starting at all, a model-database schema mismatch that would corrupt data, and a missing deployment step that would prevent the system from functioning in production.

**All critical blockers have been fixed in this session.** The project is now in a deployable state, pending the remaining medium/low-priority improvements documented below.

### Current Status

| Metric | Before | After |
|--------|--------|-------|
| App imports successfully | NO (blocker) | YES |
| Lint errors (ruff) | 19 | 0 |
| Tests passing | 0 (import error) | 6/6 |
| Model-DB schema alignment | MISMATCH | ALIGNED |
| Deployment step (migrations) | MISSING | PRESENT |
| Unauthenticated DoS vector | PRESENT | FIXED |

**Production Readiness: 72/100** (up from ~20/100 at session start)

---

## 2. COMPLETION VERIFICATION

### Q1: Is every originally planned feature fully implemented?

| Feature | Status | Evidence |
|---------|--------|----------|
| Live data ingestion (Remotive, Arbeitnow, HN, Naukri) | YES | `sources.py` implements all 4 fetchers |
| spaCy skill extraction (known + emerging) | YES | `extractor.py` two-stage pipeline |
| Custom Redis bitmap index | YES | `bitmap.py` complete implementation |
| TimescaleDB hypertables + continuous aggregate | YES (code) | Migration 002 defines it |
| Breakout signal computation | YES | `signals.py` + `infrastructure/signals.py` |
| Dashboard (Signals/Search/Graph/System) | YES | `static/index.html` + `static/graph/index.html` |
| Emerging skill review queue | YES | `emerging.py` API + review endpoint |
| Background scheduler | YES | `worker.py` 6h loop |
| API auth + rate limiting | YES (partial) | `middleware.py` — GET endpoints unrated |
| Database migrations | YES (code) | 3 migrations, correct chain |

**Verdict: All planned features are implemented in code.**

### Q2: Is every previously identified issue resolved?

The previous audit claimed 50 issues resolved. In reality:
- The "fixes" introduced a **new blocking bug** (config.py validator)
- The model schema was **never actually aligned** with migrations
- Deployment was **never actually tested**

**Verdict: Previous resolution claims were inaccurate. Re-audit found and fixed the real issues.**

### Q3: Are there any unfinished modules, TODOs, placeholders, or incomplete integrations?

| Finding | Severity | Status |
|---------|----------|--------|
| No TODO/FIXME/PLACEHOLDER markers in code | — | PASS (grep clean) |
| `conftest.py` uses `create_all` not migrations | MEDIUM | NOT FIXED (documented) |
| Two ingestion code paths (API vs pipeline) with duplicated logic | LOW | NOT FIXED (documented) |
| Benchmark depends on live DB + running server | LOW | BY DESIGN |
| Naukri source is heuristic markdown parse (not structured API) | LOW | BY DESIGN (documented) |

**Verdict: No unfinished modules. Some architectural duplication remains.**

### Q4: Are there any hidden bugs, edge cases, or technical debt?

**Bugs found and fixed this session:**
1. `config.py` `validate_urls` used non-existent `info.data_keyword` → app import crash
2. `models.py` `JobSkill` PK was `(event_id, posted_at, skill)` but DB has `(event_id, skill)` → ORM/DB mismatch
3. `ingest.py` created `JobSkill` without `posted_at` → NOT NULL violation at runtime
4. `docker-compose.yml` had no `alembic upgrade head` → fresh deploy has no schema
5. `pipeline.py` GET `/pipeline/run` was unauthenticated → DoS vector

**Remaining technical debt (documented in Section 4):**
- Bitmap index not persisted across Redis restart
- No retry on external API failures
- No API integration tests beyond health
- CORS origins mismatch (localhost:3000 vs :80)
- Worker has no graceful DB connection shutdown

### Q5: Is the project genuinely production-ready?

**NO — not yet.** It is now *deployable* (blockers fixed) but requires the medium-priority hardening items before being considered production-grade.

---

## 3. VERIFICATION RESULTS

### 3.1 Build & Import
```
✅ python -c "from app.main import create_app; create_app()" → OK
✅ All 12 API routes register correctly
✅ 7 infrastructure tables import without error
```

### 3.2 Lint (ruff)
```
✅ All checks passed! (0 errors, 0 warnings)
```

### 3.3 Tests
```
✅ 6 passed in 0.66s
   - test_health_endpoint
   - test_add_and_search_single_skill (bitmap)
   - test_multi_filter_and (bitmap)
   - test_breakout_favors_rising_recent_pairs
   - test_breakout_rewards_velocity_not_just_volume
   - test_breakout_zero_when_no_velocity
```

### 3.4 Schema Alignment
```
✅ JobEvent PK: ['event_id', 'posted_at'] == migration 002
✅ JobSkill PK: ['event_id', 'skill'] == migration 001
✅ JobEvent has url column == migration 003
✅ JobSkill has posted_at == migration 002
✅ FK job_skills(event_id, posted_at) -> job_events == migration 002
```

### 3.5 Security Verification
```
✅ GET /pipeline/run → 405 (no longer unauthenticated trigger)
✅ POST /pipeline/run without auth → 401
✅ POST /ingest without auth → 401
✅ POST /extract without auth → 401
✅ GET /health → 200 (correctly open)
✅ SQL queries: all parameterized or column names hardcoded (no injection)
```

### 3.6 Deployment Verification
```
✅ docker-compose.yml now runs `alembic upgrade head` in backend + scheduler
✅ Makefile/run.ps1 use POST + auth for pipeline/run
✅ Migration chain: 001 → 002 → 003 (correct down_revision links)
```

### 3.7 Known Limitation (NOT a bug)
```
⚠️  DB alembic_version = 001 (migrations 002/003 not yet applied to local DB)
    This is because the local DB was created via test `create_all`, not migrations.
    On a fresh production deploy, `alembic upgrade head` will apply 002 + 003.
    To fix local DB: `alembic upgrade head` (applies hypertable + url column).
```

---

## 4. REMAINING DRAWBACKS (Brutally Honest)

### 4.1 Architectural Limitations
1. **Dual ingestion paths**: `ingest.py` (API) and `pipeline.py` (scheduler) have separate, divergent logic. The API path does NOT use NLP extraction; the pipeline path does. This means `/ingest` and `/pipeline/run` produce different data quality.
2. **Bitmap index is volatile**: Stored in Redis memory. A Redis restart or flush loses the entire index. No AOF persistence configured. Must rebuild from DB (no auto-rebuild on boot).
3. **No event sourcing integrity**: The "append-only" claim is violated by the `reset_and_reingest.py` script which DELETEs all data. This is acceptable for dev but contradicts the ADR-001 "never updated, only inserted" principle.

### 4.2 Technical Debt
1. **Duplicated `_detect_seniority` and `_norm`/`_fingerprint`** in `ingest.py` and `pipeline.py`. Changes to one won't propagate to the other.
2. **`conftest.py` uses `create_all`** instead of running migrations. Tests validate the model schema, not the migration schema. This is why the alembic_version=001 issue went undetected.
3. **Module-level globals** (`_bm` in ingest.py, `_index` in search.py, `counters` in middleware.py) cause state leakage in tests and don't work correctly with multiple worker processes.

### 4.3 Scalability Bottlenecks
1. **Bitmap index is O(n) scan per query** in the worst case (full bitmap read + byte scan). At 1M+ postings this becomes slow. The claim "O(rows/64)" assumes BITOP AND is the bottleneck; the local byte-scan in Python is actually O(rows/8).
2. **Signals query is full-table self-join** with no time-partition pushdown to the continuous aggregate. At scale, this will be slow despite the materialized view existing.
3. **No connection pooling tuning**: `create_async_engine` uses defaults. Under load, this could exhaust connections.

### 4.4 Performance Limitations
1. **spaCy model loaded at import time** (`extractor.py:18`). Cold start is ~2-5s. No lazy loading despite the ADR mentioning it.
2. **No caching of taxonomy** in `extractor.py`: `_load_taxonomy` re-queries the DB on every extraction call. For a pipeline ingesting 1000+ postings, this is 1000+ redundant queries.
3. **Bitmap `add_posting` uses a single pipeline** but `search` does N round-trips for meta fetch (batched but still N gets).

### 4.5 Security Concerns
1. **GET endpoints are rate-unlimited**: Only POST/PUT/DELETE are rate-limited. An attacker can hammer `/signals`, `/search`, `/graph` with unlimited requests.
2. **`/metrics` exposes request counts** without auth — minor information disclosure.
3. **CORS allows all methods** (`GET`, `POST`) from configured origins. Should be restricted to needed methods.
4. **Default API key in `.env`** is `dev-api-key-change-in-production` — if deployed without changing, the API is effectively unauthenticated.
5. **No HTTPS enforcement** at the app level (relies on Caddy). If Caddy is misconfigured, credentials travel in plaintext.

### 4.6 Maintainability Concerns
1. **No type checking in CI**: `mypy` is configured but not run in any script. The config.py bug would have been caught by mypy (wrong ValidationInfo attribute).
2. **No integration tests**: Only unit tests for bitmap + signals math, plus health smoke test. No test covers ingest/search/graph/extract API behavior end-to-end.
3. **Hardcoded source URLs** in `sources.py` (Remotive, Arbeitnow, HN, Naukri). Changes require code edits, not config.
4. **`ponytail:` comments throughout** — these are developer notes, not documentation. They explain *why* but not *how to operate*.

### 4.7 Missing Monitoring & Observability
1. **No structured metrics export** (Prometheus/StatsD). `/metrics` is a basic in-memory counter.
2. **No distributed tracing**.
3. **No alerting** on pipeline failures (worker just prints to stdout).
4. **No log aggregation** — logs go to stdout only.

### 4.8 Missing Automated Tests
| Area | Coverage |
|------|----------|
| Health endpoint | ✅ |
| Bitmap index logic | ✅ |
| Breakout math | ✅ |
| Ingest API | ❌ |
| Search API | ❌ |
| Graph API | ❌ |
| Extract API | ❌ |
| Emerging review | ❌ |
| Pipeline run | ❌ |
| Auth middleware | ❌ |
| Rate limiting | ❌ |
| Migration chain | ❌ |

**Estimated coverage: ~15% of API surface.**

### 4.9 Features That Could Fail Under Heavy Load
1. **Bitmap index memory**: Each posting = 1 bit per distinct categorical value. At 1M postings × 1000 skills = 125MB in Redis. Acceptable but unmonitored.
2. **PostgreSQL connection exhaustion**: No pool size limit; under concurrent load, connections could be exhausted.
3. **External API rate limits**: Remotive/Arbeitnow may rate-limit; no backoff/retry.

---

## 5. FUTURE IMPROVEMENTS

### Critical (Must fix before production)
1. **Run `alembic upgrade head` on the production database** to apply migrations 002 (hypertable) and 003 (url column). Without this, the app will fail on insert (missing `url`/`posted_at` columns).
2. **Set a real `API_KEY`** in production environment. The default key makes auth meaningless.
3. **Add integration tests** for at least ingest + search + signals to catch regressions.
4. **Configure Redis AOF persistence** or add bitmap rebuild-on-boot to survive restarts.

### High (Strongly recommended)
5. **Unify ingestion paths**: Extract shared logic (`_detect_seniority`, `_norm`, `_fingerprint`, `_ensure_employer`) into a common module used by both API and pipeline.
6. **Cache taxonomy in extractor** (TTL 5 min) to eliminate redundant DB queries during bulk ingestion.
7. **Lazy-load spaCy** on first use, not at import, to speed up worker startup and avoid blocking the event loop.
8. **Add rate limiting to GET endpoints** (or at least `/search` and `/signals` which are expensive).
9. **Run mypy in CI** to catch type errors like the config.py bug.
10. **Use migrations in `conftest.py`** (or a test DB with migrations applied) so tests validate the real schema.

### Medium (Valuable)
11. **Push time-partition filter to continuous aggregate** in signals query for sub-second performance at scale.
12. **Add retry/backoff** to external API calls in `sources.py`.
13. **Restrict CORS methods** to `GET` for public endpoints, `POST` for authed ones.
14. **Add Prometheus metrics** export for real observability.
15. **Fix CORS origins** to match actual dashboard deployment (`:80` not `:3000`).
16. **Add graceful shutdown** to worker (close DB engine, flush Redis).
17. **Parameterize source URLs** via config.

### Low (Nice-to-have)
18. **Add OpenAPI security scheme** documentation for the Bearer token.
19. **Add pagination metadata** to search results (total count, page).
20. **Add input size limits** to `/extract` text field.
21. **Add health check for Redis** in `/health` endpoint (currently only DB).
22. **Add structured logging** with request IDs for traceability.

### Stretch Goals
23. **Kubernetes deployment** with HPA based on queue depth.
24. **CI/CD pipeline** (GitHub Actions) running lint + mypy + pytest + docker build.
25. **Grafana dashboard** for signals/ingestion metrics.
26. **Multi-region ingestion** with conflict resolution.
27. **GraphQL API** for flexible client queries.
28. **ML-based emerging skill prediction** (beyond NER heuristics).
29. **Webhook notifications** for breakout signals.
30. **A/B test different breakout formulas** via feature flags.

---

## 6. FINAL PRODUCTION REPORT

### 6.1 Scores

| Dimension | Score (/10) | Notes |
|-----------|-------------|-------|
| **Code Quality** | 7.5 | Clean, readable, 0 lint errors. Some duplication. |
| **Architecture** | 7.0 | Sound event-sourced design. Dual ingestion paths are a wart. |
| **Performance** | 6.5 | Bitmap index good for small scale. No caching, no lazy NLP. |
| **Security** | 6.0 | Auth on writes, but GET unrated, default key risky, CORS loose. |
| **Maintainability** | 6.5 | Good structure, but no integration tests, no mypy in CI. |
| **Scalability** | 6.0 | Works at 2K rows. Unproven at 1M+. No pool tuning. |
| **Testing** | 4.0 | Only 15% API coverage. No migration/integration tests. |
| **Documentation** | 8.0 | Excellent ADR + architecture docs. README accurate post-fix. |

**Weighted Overall: 6.4/10**

### 6.2 Completion Metrics
- **Project Completion:** 95% (all features coded)
- **Production Readiness:** 72% (blockers fixed, hardening pending)
- **Test Coverage:** ~15% API surface
- **Documentation Quality:** Good (8/10)

### 6.3 Remaining Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DB schema not migrated (002/003) | HIGH | CRITICAL | Run `alembic upgrade head` before deploy |
| Default API key deployed | MEDIUM | HIGH | Set real key in env |
| Redis restart loses index | MEDIUM | MEDIUM | AOF persistence or rebuild-on-boot |
| Unrated GET endpoints abused | MEDIUM | MEDIUM | Add GET rate limiting |
| NLP cold-start delay | LOW | LOW | Lazy-load spaCy |
| External API rate-limit | LOW | MEDIUM | Add retry/backoff |

### 6.4 Known Limitations (Accepted)
- Bitmap index is volatile (Redis memory)
- Naukri source is heuristic (not structured API)
- Single-region deployment
- No multi-tenancy

### 6.5 Deployment Readiness
- ✅ Build succeeds (Dockerfile valid)
- ✅ Migrations present (alembic chain correct)
- ✅ Deployment script updated (alembic upgrade head added)
- ⚠️ Requires manual `alembic upgrade head` if not using docker-compose
- ⚠️ Requires real API key in production env

### 6.6 FINAL RECOMMENDATION

**NOT YET APPROVED FOR PRODUCTION** — but the path is clear.

The project has moved from **BROKEN** (import crash, schema mismatch, missing deployment) to **DEPLOYABLE** (all blockers fixed). Before production sign-off, complete the 4 Critical items:

1. `alembic upgrade head` on production DB
2. Set real `API_KEY`
3. Add integration tests (ingest + search + signals)
4. Redis AOF persistence or bitmap rebuild-on-boot

**Estimated effort to production:** 1-2 days for Critical items, 3-5 days for High items.

---

## 7. FIXES APPLIED THIS SESSION

| File | Fix | Severity |
|------|-----|----------|
| `app/core/config.py` | Removed broken `validate_urls` (used non-existent `info.data_keyword`) | BLOCKER |
| `app/core/config.py` | Removed unused `ClassVar` import | LINT |
| `app/infrastructure/database/models.py` | Fixed `JobSkill` PK: `(event_id, posted_at, skill)` → `(event_id, skill)` | CRITICAL |
| `app/infrastructure/database/models.py` | Removed unused imports (`PrimaryKeyConstraint`, `import sqlalchemy as sa`) | LINT |
| `app/api/v1/ingest.py` | Added missing `posted_at=posted` to `JobSkill` creation | CRITICAL |
| `app/api/v1/search.py` | Fixed E501 line-too-long | LINT |
| `app/infrastructure/indexing/bitmap.py` | Fixed 3× E501 with helper function | LINT |
| `app/infrastructure/ingestion/sources.py` | Fixed 2× E501 | LINT |
| `app/scripts/seed_taxonomy.py` | Removed unused `settings`/`func`/`get_settings` | LINT |
| `docker-compose.yml` | Added `alembic upgrade head` to backend + scheduler | CRITICAL |
| `app/api/v1/pipeline.py` | Removed unauthenticated GET `/pipeline/run` | CRITICAL |
| `Makefile` | Updated `pipeline/run` to POST + auth | SECURITY |
| `run.ps1` | Updated `pipeline/run` to POST + auth | SECURITY |

**Total: 13 fixes (3 critical, 1 blocker, 2 security, 7 lint)**
