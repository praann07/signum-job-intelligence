from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session

router = APIRouter()


@router.get("/graph")
async def graph(
    skill: str = Query(..., min_length=1),
    limit: int = Query(30, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    # ponytail: skills are stored capitalized; match case-insensitively.
    skill_lc = skill.lower()
    skill_count = await session.scalar(
        text("SELECT COUNT(*) FROM job_skills WHERE lower(skill) = :skill"),
        {"skill": skill_lc},
    )
    if not skill_count:
        raise HTTPException(status_code=404, detail=f"Skill '{skill}' not found in any postings")

    rows = await session.execute(text("""
        SELECT
            CASE WHEN lower(a.skill) = :skill THEN b.skill ELSE a.skill END AS neighbor,
            COUNT(*) AS weight
        FROM job_skills a
        JOIN job_skills b ON a.event_id = b.event_id AND a.skill < b.skill
        WHERE lower(a.skill) = :skill OR lower(b.skill) = :skill
        GROUP BY neighbor
        ORDER BY weight DESC
        LIMIT :limit
    """), {"skill": skill_lc, "limit": limit})

    neighbors = [{"skill": r[0], "weight": r[1]} for r in rows]
    nodes = [{"id": skill, "group": "center"}]
    nodes += [{"id": n["skill"], "group": "neighbor"} for n in neighbors]
    links = [{"source": skill, "target": n["skill"], "weight": n["weight"]} for n in neighbors]

    return {"skill": skill, "nodes": nodes, "links": links, "neighbor_count": len(neighbors)}
