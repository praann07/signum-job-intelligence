from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.deps import get_session
from app.core.config import get_settings
from app.infrastructure.database.models import JobEvent, JobSkill
from app.infrastructure.indexing.bitmap import BitmapIndex
from app.infrastructure.ingestion.common import (
    _fingerprint,
    detect_seniority,
    ensure_employer,
)

router = APIRouter()
logger = get_logger()


class SkillInput(BaseModel):
    skill: str
    is_known: bool = True
    extraction_confidence: float | None = None


class PostingInput(BaseModel):
    title: str
    company: str
    source: str = "manual"
    location: str | None = None
    country: str = "unknown"
    seniority: str | None = None
    posted_at: datetime | None = None
    skills: list[SkillInput] = []


class IngestRequest(BaseModel):
    postings: list[PostingInput]


_bm: BitmapIndex | None = None


def _get_bm() -> BitmapIndex:
    global _bm
    if _bm is None:
        _bm = BitmapIndex(get_settings().redis_url)
    return _bm


@router.post("/ingest")
async def ingest_postings(
    body: IngestRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    inserted = 0
    skipped = 0
    bm = _get_bm()
    for p in body.postings:
        fp = _fingerprint(p.title, p.company, p.location)
        existing = await session.execute(select(JobEvent).where(JobEvent.fingerprint == fp))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        employer = await ensure_employer(session, p.company)

        posted = p.posted_at or datetime.now(UTC)
        event = JobEvent(
            event_id=uuid4(),
            company_id=employer.company_id,
            source=p.source,
            location=p.location,
            country=p.country,
            seniority=p.seniority or detect_seniority(p.title),
            title=p.title,
            posted_at=posted,
            fingerprint=fp,
        )
        session.add(event)
        await session.flush()

        for s in p.skills:
            session.add(
                JobSkill(
                    event_id=event.event_id,
                    skill=s.skill,
                    posted_at=posted,
                    is_known=s.is_known,
                    extraction_confidence=s.extraction_confidence,
                )
            )
        inserted += 1

        posting_number = await bm.next_index()
        skill_names = [s.skill for s in p.skills]
        await bm.add_posting(
            posting_number,
            event.event_id,
            skill_names,
            seniority=p.seniority or detect_seniority(p.title),
            country=p.country if p.country not in ("unknown",) else None,
            company_size=employer.size if employer.size != "unknown" else None,
        )

    try:
        await session.commit()
    except IntegrityError as exc:
        logger.error("ingest_commit_failed", error=str(exc))
        await session.rollback()
        result = await session.execute(select(JobEvent))
        all_events = result.scalars().all()
        inserted = len(all_events)
        skipped = sum(1 for _ in body.postings) - inserted

    logger.info("ingest_complete", inserted=inserted, skipped=skipped)
    return {"inserted": inserted, "skipped": skipped}
