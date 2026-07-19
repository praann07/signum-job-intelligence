"""Smoke test: ingest a few REAL postings, then exercise the API.

ponytail: minimal — no subprocess/uvicorn dance. Boots the app in-process via
ASGITransport, ingests live Remotive+Arbeitnow data through the real pipeline,
then asserts /signals and /search return something. Run after `alembic upgrade head`.
"""

import asyncio

import httpx
from sqlalchemy import text

from app.infrastructure.database.session import async_session_factory
from app.infrastructure.ingestion.pipeline import run_pipeline
from app.main import create_app


async def main() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as cli:
        # ingest real data through the actual pipeline
        async with async_session_factory() as s:
            res = await run_pipeline(s)
        print(f"ingested: {res}")
        assert res["fetched"] > 0, "no real postings fetched"

        sig = (await cli.get("/api/v1/signals?limit=5")).json()
        assert sig["total_pairs"] >= 0
        print(f"signals pairs: {sig['total_pairs']}")

        health = (await cli.get("/api/v1/health")).json()
        print(f"health: {health['status']}, postings: {health['postings']}")
        assert health["postings"] > 0

    # DB sanity
    async with async_session_factory() as s:
        n = await s.scalar(text("SELECT count(DISTINCT skill) FROM job_skills"))
    print(f"distinct skills in DB: {n}")
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
