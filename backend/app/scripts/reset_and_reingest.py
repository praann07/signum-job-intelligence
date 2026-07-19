"""Reset job data and re-ingest with the (now expanded) skill taxonomy.

Clears postings/cooccurrence/emerging but KEEPS the seeded skill_taxonomy,
then re-runs the live pipeline so the 60~ live postings get re-extracted with
the full skill set.

Run:  python -m app.scripts.reset_and_reingest
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.indexing.bitmap import BitmapIndex
from app.infrastructure.ingestion.pipeline import run_pipeline

TABLES = ["job_skills", "job_events", "skill_cooccurrence", "emerging_candidates"]
# ponytail: hard-reset the bitmap keys so the index is rebuilt from scratch.
REDIS_PATTERNS = ["bm:*", "idx:*", "meta:*", "posting_counter"]


async def reset_and_reingest() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        for t in TABLES:
            await session.execute(text(f"DELETE FROM {t}"))
        await session.commit()
        print("cleared postings/cooccurrence/emerging")

    # flush bitmap index keys
    bm = BitmapIndex(settings.redis_url)
    for pat in REDIS_PATTERNS:
        keys = await bm.redis.keys(pat)
        if keys:
            await bm.redis.delete(*keys)
    print("flushed redis bitmap index")

    async with async_session_factory() as session:
        result = await run_pipeline(session)
        print("re-ingest result:", result)


if __name__ == "__main__":
    asyncio.run(reset_and_reingest())
