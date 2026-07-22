import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.infrastructure.database.models import PipelineRun
from app.infrastructure.ingestion.pipeline import run_pipeline

router = APIRouter()


@router.post("/pipeline/run")
async def pipeline_run(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    """Trigger a real-data ingestion run.

    Requires the API key (enforced by AuthMiddleware on POST). Use the Makefile/
    run.ps1 `ingest` target or curl with `-H "Authorization: Bearer <KEY>"`.
    """
    return await run_pipeline(session)


@router.get("/pipeline/status")
async def pipeline_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    postings, skills, emerging = await asyncio.gather(
        session.scalar(text("SELECT COUNT(*) FROM job_events")),
        session.scalar(text("SELECT COUNT(DISTINCT skill) FROM job_skills")),
        session.scalar(text("SELECT COUNT(*) FROM emerging_candidates WHERE reviewed = FALSE")),
    )

    rows = await session.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(20)
    )
    runs = [
        {
            "source": r.source,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "fetched": r.fetched,
            "inserted": r.inserted,
            "skipped": r.skipped,
            "error": r.error,
            "duration_ms": r.duration_ms,
        }
        for r in rows.scalars().all()
    ]

    return {
        "postings": postings or 0,
        "distinct_skills": skills or 0,
        "unreviewed_emerging": emerging or 0,
        "sources": ["remotive", "arbeitnow", "hackernews", "naukri"],
        "recent_runs": runs,
    }
