from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session

router = APIRouter()

# ponytail: interval is validated by regex, safe for substitution
_TREND_QUERY_TMPL = """
    SELECT
        time_bucket(INTERVAL '{interval}', je.posted_at) AS bucket,
        COUNT(*)::int AS count
    FROM job_skills js
    JOIN job_events je ON je.event_id = js.event_id
    WHERE js.skill = :skill
      AND je.posted_at >= NOW() - (:months || ' days')::interval
    GROUP BY bucket
    ORDER BY bucket
"""


@router.get("/trends")
async def skill_trends(
    skill: str = Query(..., min_length=1),
    interval: str = Query("7 days", pattern="^(1 day|7 days|30 days)$"),
    months: int = Query(6, ge=1, le=24),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    rows = await session.execute(
        text(_TREND_QUERY_TMPL.format(interval=interval)),
        {"skill": skill, "months": str(months * 30)},
    )
    data = [{"bucket": r[0].isoformat(), "count": r[1]} for r in rows]
    total = sum(d["count"] for d in data) if data else 0
    # ponytail: simple linear trend direction from first vs last half
    trend: str = "flat"
    if len(data) >= 4:
        mid = len(data) // 2
        first_half = sum(d["count"] for d in data[:mid])
        second_half = sum(d["count"] for d in data[mid:])
        ratio = second_half / max(first_half, 1)
        if ratio > 1.15:
            trend = "up"
        elif ratio < 0.85:
            trend = "down"

    return {
        "skill": skill,
        "interval": interval,
        "months": months,
        "total": total,
        "trend": trend,
        "data": data,
    }
