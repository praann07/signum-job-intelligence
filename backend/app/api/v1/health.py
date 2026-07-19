from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.deps import get_session

router = APIRouter()
logger = get_logger()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    db_ok = False
    posting_count = 0
    try:
        result = await session.execute(text("SELECT COUNT(*) FROM job_events"))
        posting_count = result.scalar() or 0
        db_ok = True
    except Exception:
        db_ok = False
        logger.warning("health_check_db_unreachable")

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "postings": posting_count,
    }
