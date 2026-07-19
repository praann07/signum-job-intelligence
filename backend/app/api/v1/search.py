from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.infrastructure.indexing.bitmap import BitmapIndex

router = APIRouter()
_index: BitmapIndex | None = None


def get_index() -> BitmapIndex:
    global _index
    if _index is None:
        _index = BitmapIndex(get_settings().redis_url)
    return _index


@router.get("/search")
async def search(
    skills: list[str] = Query([]),
    seniority: str | None = Query(None),
    country: str | None = Query(None),
    company_size: str | None = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    raw_filters: dict[str, str | None] = {
        "sen": seniority,
        "country": country,
        "size": company_size,
    }
    filters: dict[str, str] = {k: v for k, v in raw_filters.items() if v}

    try:
        idx = get_index()
        results = await idx.search(skills, filters, limit)
        if results:
            # ponytail: bitmap rows store title/source but not url; backfill
            # url (and any missing title/source) from DB in one query.
            missing = [r["event_id"] for r in results if not r.get("title") or "url" not in r]
            if missing:
                rows = await session.execute(
                    text(
                        "SELECT event_id, title, source, url "
                        "FROM job_events WHERE event_id = ANY(:ids)"
                    ),
                    {"ids": [r["event_id"] for r in results]},
                )
                meta = {str(r[0]): (r[1], r[2], r[3]) for r in rows}
                for r in results:
                    if r["event_id"] in meta:
                        r["title"], r["source"], r["url"] = meta[r["event_id"]]
            return {
                "skills": skills,
                "filters": filters,
                "method": "redis_bitmap",
                "matches": len(results),
                "results": results,
            }
    except Exception:
        pass

    # ponytail: Redis down/empty — parameterized B-tree fallback (no injection).
    params: dict[str, object] = {"limit": limit}
    clauses: list[str] = []
    if skills:
        clauses.append("js.skill = ANY(:skills)")
        params["skills"] = [s.lower() for s in skills]
    for fld, col in (
        ("seniority", "e.seniority"),
        ("country", "e.country"),
        ("company_size", "em.size"),
    ):
        val = filters.get(fld)
        if val:
            clauses.append(f"{col} = :{fld}")
            params[fld] = val

    where = " AND ".join(clauses) if clauses else "1=1"
    needs_employer = "em.size" in where
    join_employer = "JOIN employers em ON em.company_id = e.company_id" if needs_employer else ""
    sql = text(f"""
        SELECT e.event_id, e.title, e.source, e.url
        FROM job_events e
        JOIN job_skills js ON e.event_id = js.event_id
        {join_employer}
        WHERE {where}
        GROUP BY e.event_id, e.title, e.source, e.url, e.posted_at
        HAVING COUNT(DISTINCT js.skill) = :nskills
        ORDER BY e.posted_at DESC
        LIMIT :limit
    """)
    params["nskills"] = len(skills)
    rows = await session.execute(sql, params)
    results = [{"event_id": str(r[0]), "title": r[1], "source": r[2], "url": r[3]} for r in rows]
    return {
        "skills": skills,
        "filters": filters,
        "method": "postgres_btree",
        "matches": len(results),
        "results": results,
    }
