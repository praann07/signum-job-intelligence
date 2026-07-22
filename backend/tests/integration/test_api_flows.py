"""Integration tests for the core API endpoints: ingest, search, signals.

These exercise the full request path (AuthMiddleware + RateLimitMiddleware +
route handlers) against a live (test) database and Redis bitmap index.

Note: tests run against the already-migrated dev database (schema applied via
`alembic upgrade head`). conftest truncates tables per test rather than
recreating them, which avoids TimescaleDB hypertable drop races.
"""

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.fixture
def auth_headers() -> dict[str, str]:
    from app.core.config import get_settings

    return {"Authorization": f"Bearer {get_settings().api_key}"}


@pytest.mark.asyncio
async def test_ingest_requires_auth(api_client: AsyncClient):
    payload = {
        "postings": [
            {
                "title": "Senior Python Engineer",
                "company": "TestCorp",
                "source": "manual",
                "location": "Remote",
                "country": "us",
                "skills": [{"skill": "python", "is_known": True}],
            }
        ]
    }
    # No auth header -> 401
    resp = await api_client.post("/api/v1/ingest", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_and_search_flow(api_client: AsyncClient, auth_headers: dict[str, str]):
    payload = {
        "postings": [
            {
                "title": "Senior Python Engineer",
                "company": "TestCorp",
                "source": "manual",
                "location": "Remote",
                "country": "us",
                "skills": [
                    {"skill": "python", "is_known": True},
                    {"skill": "docker", "is_known": True},
                ],
            }
        ]
    }
    resp = await api_client.post("/api/v1/ingest", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1

    # Search should find the posting by skill
    search_resp = await api_client.get("/api/v1/search", params={"skills": ["python"], "limit": 10})
    assert search_resp.status_code == 200
    sbody = search_resp.json()
    assert sbody["matches"] >= 1
    assert any("Python" in r.get("title", "") for r in sbody["results"])


@pytest.mark.asyncio
async def test_ingest_dedup_by_fingerprint(api_client: AsyncClient, auth_headers: dict[str, str]):
    payload = {
        "postings": [
            {
                "title": "Junior Java Dev",
                "company": "DupCorp",
                "skills": [{"skill": "java", "is_known": True}],
            }
        ]
    }
    r1 = await api_client.post("/api/v1/ingest", json=payload, headers=auth_headers)
    r2 = await api_client.post("/api/v1/ingest", json=payload, headers=auth_headers)
    assert r1.json()["inserted"] == 1
    assert r2.json()["skipped"] == 1
    assert r2.json()["inserted"] == 0


@pytest.mark.asyncio
async def test_signals_endpoint_returns_list(api_client: AsyncClient):
    resp = await api_client.get("/api/v1/signals", params={"limit": 10, "window_days": 30})
    assert resp.status_code == 200
    body = resp.json()
    # signals endpoint returns either a list or a dict with pairs
    assert isinstance(body, (list, dict))


@pytest.mark.asyncio
async def test_search_fallback_when_redis_down(
    api_client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """If the bitmap search fails, the endpoint should fall back to Postgres."""
    # First ingest
    payload = {
        "postings": [
            {
                "title": "Go Backend Engineer",
                "company": "FallbackCorp",
                "skills": [{"skill": "go", "is_known": True}],
            }
        ]
    }
    await api_client.post("/api/v1/ingest", json=payload, headers=auth_headers)

    # Force bitmap search to raise
    from app.infrastructure.indexing import bitmap as bitmap_mod

    async def _boom(*args: object, **kwargs: object) -> list[dict]:
        raise RuntimeError("redis simulated down")

    monkeypatch.setattr(bitmap_mod.BitmapIndex, "search", _boom)

    resp = await api_client.get("/api/v1/search", params={"skills": ["go"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "postgres_btree"
    assert body["matches"] >= 1


@pytest.mark.asyncio
async def test_bitmap_rebuild_from_db(
    api_client: AsyncClient, auth_headers: dict[str, str], db_session
):
    """Bitmap index must be reconstructable from the DB after Redis loss."""

    from app.infrastructure.indexing.bitmap import BitmapIndex

    # Ingest some data
    payload = {
        "postings": [
            {
                "title": "Rust Systems Engineer",
                "company": "RebuildCorp",
                "skills": [{"skill": "rust", "is_known": True}],
            }
        ]
    }
    await api_client.post("/api/v1/ingest", json=payload, headers=auth_headers)

    # Simulate Redis losing all data
    bm = BitmapIndex(get_settings().redis_url)
    for pat in ("bm:*", "idx:*", "meta:*", "posting_counter"):
        keys = await bm.redis.keys(pat)
        if keys:
            await bm.redis.delete(*keys)

    # Rebuild from DB
    rebuilt = await bm.rebuild_from_db(db_session)
    assert rebuilt >= 1

    # Search should now find the posting via the rebuilt index
    res = await bm.search(["rust"])
    assert len(res) >= 1
    assert any("Rust" in r["title"] for r in res)
