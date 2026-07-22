from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
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

    @field_validator("postings")
    @classmethod
    def check_size(cls, v: list[PostingInput]) -> list[PostingInput]:
        if len(v) > 500:
            raise ValueError("Max 500 postings per ingest batch")
        return v


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
    pending: list[dict[str, object]] = []
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

        pending.append(
            {
                "event_id": event.event_id,
                "skills": [s.skill for s in p.skills],
                "seniority": p.seniority or detect_seniority(p.title),
                "country": p.country if p.country not in ("unknown",) else None,
                "company_size": employer.size if employer.size != "unknown" else None,
                "posted_at": posted.isoformat() if posted else None,
            }
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
        pending.clear()

    # ponytail: bitmap writes MUST happen AFTER successful DB commit so a
    # failed commit can't leave the index with stale data that has no DB row.
    bm = _get_bm()
    for p in pending:
        posting_number = await bm.next_index()
        await bm.add_posting(
            posting_number,
            p["event_id"],
            p["skills"],
            seniority=p["seniority"],
            country=p["country"],
            company_size=p["company_size"],
            posted_at=p["posted_at"],
        )

    logger.info("ingest_complete", inserted=inserted, skipped=skipped)
    return {"inserted": inserted, "skipped": skipped}
