from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.infrastructure.signals import breakout_score

router = APIRouter()

_CAGG_QUERY = """
    SELECT skill_a, skill_b,
        SUM(pair_count)::int AS total,
        MIN(first_seen) AS first_seen,
        MAX(last_seen) AS last_seen,
        SUM(pair_count) FILTER (
            WHERE bucket >= NOW() - INTERVAL '7 days'
        )::int AS last7,
        COALESCE(SUM(pair_count), 0)::int AS recent
    FROM cooccurrence_30d
    WHERE bucket >= NOW() - INTERVAL '30 days'::interval
    GROUP BY skill_a, skill_b
    HAVING SUM(pair_count) >= 3
"""

_RAW_QUERY = """
    SELECT
        a.skill AS skill_a,
        b.skill AS skill_b,
        COUNT(*) AS pair_count,
        MIN(e.posted_at) AS first_seen,
        MAX(e.posted_at) AS last_seen,
        COUNT(*) FILTER (WHERE e.posted_at >= NOW() - INTERVAL '7 days') AS last7,
        COUNT(*) FILTER (WHERE e.posted_at >= NOW() - (:window || ' days')::interval) AS recent
    FROM job_skills a
    JOIN job_skills b ON a.event_id = b.event_id AND a.skill < b.skill
    JOIN job_events e ON e.event_id = a.event_id
    GROUP BY a.skill, b.skill
    HAVING COUNT(*) >= 3
"""


@router.get("/signals")
async def signals(
    limit: int = Query(20, le=100),
    window_days: int = Query(30, le=365),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    # ponytail: for window <= 30 days, use the materialised CAGG (faster).
    # Fall back to raw tables for larger windows or when CAGG is empty.
    use_cagg = window_days <= 30
    params: dict[str, object] = {"window": str(window_days)}
    if use_cagg:
        try:
            rows = await session.execute(text(_CAGG_QUERY))
            # If CAGG returns nothing, fall through to raw tables
            if rows.rowcount is None or rows.rowcount > 0:
                use_cagg = True
            _rows = rows.fetchall()
            if not _rows:
                use_cagg = False
                rows = await session.execute(text(_RAW_QUERY), params)
            else:
                rows = _rows
        except Exception:
            use_cagg = False
            rows = await session.execute(text(_RAW_QUERY), params)
    else:
        rows = await session.execute(text(_RAW_QUERY), params)

    now = datetime.now(UTC)
    scored = []
    for skill_a, skill_b, total, first, last, last7, recent in rows:
        if not first:
            continue
        prior = max(total - recent, 0)
        score = breakout_score(total, recent, prior, first, now)
        velocity = recent - prior
        days_since = max((now - first).days, 1)
        novelty = 1.0 / (days_since + 1)
        scored.append(
            {
                "skill_a": skill_a,
                "skill_b": skill_b,
                "pair_count": total,
                "recent": recent,
                "last7": last7,
                "first_seen": first.isoformat(),
                "last_seen": last.isoformat() if last else None,
                "velocity": velocity,
                "novelty": round(novelty, 4),
                "breakout_score": score,
                "from_cagg": use_cagg,
            }
        )

    scored.sort(key=lambda r: r["breakout_score"], reverse=True)
    return {"signals": scored[:limit], "total_pairs": len(scored)}
