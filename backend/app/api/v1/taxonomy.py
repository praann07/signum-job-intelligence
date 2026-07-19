"""Distinct skills present in the index.

Returns the skills that actually appear in `job_skills` so the frontend can
offer only searchable chips instead of a hardcoded list.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session

router = APIRouter()


@router.get("/taxonomy")
async def list_skills(
    limit: int = Query(200, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    rows = await session.execute(
        text("SELECT DISTINCT skill FROM job_skills ORDER BY skill LIMIT :limit"),
        {"limit": limit},
    )
    skills = [r[0] for r in rows]
    return {"skills": skills, "count": len(skills)}
