"""Ingestion pipeline: real sources -> skill extraction -> DB + bitmap index."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database.models import EmergingCandidate, JobEvent, JobSkill
from app.infrastructure.extraction.extractor import extract_from_text
from app.infrastructure.indexing.bitmap import BitmapIndex
from app.infrastructure.ingestion.common import (
    _fingerprint,
    detect_seniority,
    ensure_employer,
    parse_posted_at,
)
from app.infrastructure.ingestion.sources import (
    RawPosting,
    fetch_arbeitnow,
    fetch_hackernews,
    fetch_naukri,
    fetch_remotive,
)

_size_hints = {
    "startup": "early", "seed": "seed", "incubat": "seed",
    "series": "mid", "scale": "late", "enterprise": "public",
    "unicorn": "late", "public": "public",
}


def _fingerprint_from_posting(p: RawPosting) -> str:
    return _fingerprint(p.title, p.company or "unknown", p.location)


async def _record_emerging(session: AsyncSession, tokens: list[str]) -> None:
    for tok in tokens:
        res = await session.execute(select(EmergingCandidate).where(EmergingCandidate.token == tok))
        rec = res.scalar_one_or_none()
        if rec:
            rec.occurrence_count += 1
        else:
            session.add(EmergingCandidate(token=tok))


async def ingest_raw(session: AsyncSession, bm: BitmapIndex, p: RawPosting) -> str:
    """Returns 'inserted' or 'skipped'."""
    fp = _fingerprint_from_posting(p)
    exists = await session.execute(select(JobEvent).where(JobEvent.fingerprint == fp))
    if exists.scalar_one_or_none():
        return "skipped"

    employer = await ensure_employer(session, p.company or "unknown")
    known, emerging = await extract_from_text(session, p.title, p.description)
    if not known:
        known = [{"skill": t, "is_known": True, "extraction_confidence": 0.8} for t in p.tags[:8]]
    if not known:
        return "skipped"

    posted = parse_posted_at(p.posted_at)

    event = JobEvent(
        event_id=uuid4(),
        company_id=employer.company_id,
        source=p.source or "unknown",
        url=p.url,
        location=p.location,
        country=p.country,
        seniority=detect_seniority(p.title),
        title=p.title,
        posted_at=posted,
        fingerprint=fp,
    )
    session.add(event)
    await session.flush()

    for s in known:
        session.add(JobSkill(
            event_id=event.event_id,
            posted_at=event.posted_at,
            skill=s["skill"],
            is_known=s.get("is_known", True),
            extraction_confidence=s.get("extraction_confidence"),
        ))
    await _record_emerging(session, emerging)

    n = await bm.next_index()
    await bm.add_posting(
        n, event.event_id,
        [str(s["skill"]) for s in known],
        seniority=detect_seniority(p.title),
        country=p.country if p.country not in ("unknown", "remote", "eu") else None,
        company_size=employer.size if employer.size != "unknown" else None,
        title=p.title,
        source=p.source,
        url=p.url,
    )
    return "inserted"


async def run_pipeline(session: AsyncSession) -> dict[str, object]:
    bm = BitmapIndex(get_settings().redis_url)
    sources: list[RawPosting] = []
    sources += await fetch_remotive()
    sources += await fetch_arbeitnow()
    sources += await fetch_hackernews()
    sources += await fetch_naukri(get_settings().firecrawl_api_key)

    inserted = skipped = 0
    for p in sources:
        status = await ingest_raw(session, bm, p)
        if status == "inserted":
            inserted += 1
        else:
            skipped += 1
        if (inserted + skipped) % 50 == 0:
            await session.commit()
    await session.commit()
    return {"fetched": len(sources), "inserted": inserted, "skipped": skipped}
