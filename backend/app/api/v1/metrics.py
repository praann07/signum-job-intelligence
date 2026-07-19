import time

from fastapi import APIRouter

from app.api.middleware import counters

router = APIRouter()
start_time = time.time()


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    return {
        "uptime_seconds": round(time.time() - start_time),
        "requests_total": dict(counters),
    }
