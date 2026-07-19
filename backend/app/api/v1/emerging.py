"""Review queue for skills discovered by the NER pipeline.

The extractor flags unknown noun chunks as `emerging_candidates`. A human
(you) reviews them here: accept (promote into the taxonomy) or reject.
This closes the loop from "discovery" to "known skill".
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.infrastructure.database.models import EmergingCandidate, SkillTaxonomy

router = APIRouter()


@router.get("/emerging")
async def list_emerging(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    rows = await session.execute(
        select(EmergingCandidate)
        .where(EmergingCandidate.reviewed == False)  # noqa: E712
        .order_by(EmergingCandidate.occurrence_count.desc())
        .limit(limit)
    )
    items = [
        {
            "token": c.token,
            "occurrence_count": c.occurrence_count,
            "first_seen": c.first_seen.isoformat() if c.first_seen else None,
        }
        for c in rows.scalars().all()
    ]
    return {"candidates": items, "count": len(items)}


class ReviewRequest(BaseModel):
    token: str
    accept: bool
    category: str | None = None
    reason: str | None = None


@router.post("/emerging/review")
async def review_emerging(
    body: ReviewRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    res = await session.execute(
        select(EmergingCandidate).where(EmergingCandidate.token == body.token)
    )
    cand = res.scalar_one_or_none()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cand.reviewed = True
    cand.accepted = body.accept
    cand.reviewed_at = datetime.now(UTC)
    cand.rejection_reason = body.reason

    if body.accept:
        session.add(
            SkillTaxonomy(
                skill=body.token,
                category=body.category or "tool",
                added_by="manual",
            )
        )
    await session.commit()
    return {"token": body.token, "accepted": body.accept}
