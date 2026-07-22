"""Ingestion pipeline: real sources -> skill extraction -> DB + bitmap index."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.core.config import get_settings
from app.infrastructure.database.models import EmergingCandidate, JobEvent, JobSkill, PipelineRun
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
    fetch_adzuna,
    fetch_arbeitnow,
    fetch_hackernews,
    fetch_naukri,
    fetch_remotive,
)

logger = get_logger(__name__)

_size_hints = {
    "startup": "early",
    "seed": "seed",
    "incubat": "seed",
    "series": "mid",
    "scale": "late",
    "enterprise": "public",
    "unicorn": "late",
    "public": "public",
}


@dataclass
class _PendingBitmap:
    event_id: UUID
    skills: list[str]
    seniority: str | None
    country: str | None
    company_size: str | None
    title: str | None
    source: str | None
    url: str | None
    posted_at: str | None


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


async def ingest_raw(session: AsyncSession, p: RawPosting) -> tuple[str, _PendingBitmap | None]:
    """Returns ('inserted', pending_data) or ('skipped', None)."""
    fp = _fingerprint_from_posting(p)
    exists = await session.execute(select(JobEvent).where(JobEvent.fingerprint == fp))
    if exists.scalar_one_or_none():
        return "skipped", None

    employer = await ensure_employer(session, p.company or "unknown")
    known, emerging = await extract_from_text(session, p.title, p.description)
    if not known:
        known = [{"skill": t, "is_known": True, "extraction_confidence": 0.8} for t in p.tags[:8]]
    if not known:
        return "skipped", None

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
        session.add(
            JobSkill(
                event_id=event.event_id,
                posted_at=event.posted_at,
                skill=s["skill"],
                is_known=s.get("is_known", True),
                extraction_confidence=s.get("extraction_confidence"),
            )
        )
    await _record_emerging(session, emerging)

    return "inserted", _PendingBitmap(
        event_id=event.event_id,
        skills=[str(s["skill"]) for s in known],
        seniority=detect_seniority(p.title),
        country=p.country if p.country not in ("unknown", "remote", "eu") else None,
        company_size=employer.size if employer.size != "unknown" else None,
        title=p.title,
        source=p.source,
        url=p.url,
        posted_at=posted.isoformat() if posted else None,
    )


async def run_pipeline(session: AsyncSession) -> dict[str, object]:
    bm = BitmapIndex(get_settings().redis_url)

    s = get_settings()
    source_fetchers: list[tuple[str, object]] = [
        ("remotive", fetch_remotive()),
        ("arbeitnow", fetch_arbeitnow()),
        ("hackernews", fetch_hackernews()),
        ("adzuna", fetch_adzuna(s.adzuna_app_id, s.adzuna_api_key)),
        ("naukri", fetch_naukri(s.firecrawl_api_key)),
    ]

    # ponytail: one failing source must not abort the whole pipeline. Process
    # each source independently so a bad API response only affects its own run.
    per_source: list[dict[str, object]] = []
    total_fetched = total_inserted = total_skipped = 0

    for name, coro in source_fetchers:
        start = time.monotonic()
        error: str | None = None
        postings: list[RawPosting] = []
        try:
            postings = await coro
        except Exception as e:
            error = str(e)
            logger.warning("source_fetch_failed", source=name, error=str(e))

        fetched = len(postings)
        inserted = skipped = 0
        pending: list[_PendingBitmap] = []

        for p in postings:
            status, pb = await ingest_raw(session, p)
            if status == "inserted":
                inserted += 1
                if pb:
                    pending.append(pb)
            else:
                skipped += 1
            if (inserted + skipped) % 50 == 0:
                await session.commit()
                await _flush_bitmaps(bm, pending)

        await session.commit()
        await _flush_bitmaps(bm, pending)

        duration_ms = int((time.monotonic() - start) * 1000)
        per_source.append(
            {
                "source": name,
                "fetched": fetched,
                "inserted": inserted,
                "skipped": skipped,
                "error": error,
                "duration_ms": duration_ms,
            }
        )

        run = PipelineRun(
            run_id=uuid4(),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            source=name,
            fetched=fetched,
            inserted=inserted,
            skipped=skipped,
            error=error,
            duration_ms=duration_ms,
        )
        session.add(run)
        total_fetched += fetched
        total_inserted += inserted
        total_skipped += skipped

    await session.commit()

    # ponytail: refresh the 30-day co-occurrence CAGG so /signals can read
    # materialized data instead of scanning raw tables.
    try:
        await session.execute(
            text(
                "CALL refresh_continuous_aggregate("
                "'cooccurrence_30d', NOW() - INTERVAL '31 days', NOW())"
            )
        )
        await session.commit()
    except Exception as e:
        logger.warning("cagg_refresh_failed", error=str(e))

    return {
        "fetched": total_fetched,
        "inserted": total_inserted,
        "skipped": total_skipped,
        "sources": per_source,
    }


async def _flush_bitmaps(bm: BitmapIndex, pending: list[_PendingBitmap]) -> None:
    """Write pending bitmap entries after a commit batch completes."""
    if not pending:
        return
    for pb in pending:
        n = await bm.next_index()
        await bm.add_posting(
            n,
            pb.event_id,
            pb.skills,
            seniority=pb.seniority,
            country=pb.country,
            company_size=pb.company_size,
            title=pb.title,
            source=pb.source,
            url=pb.url,
            posted_at=pb.posted_at,
        )
    pending.clear()
