"""Background scheduler: ingests real job data every 6 hours.

Run with:  python -m app.worker
ponytail: plain asyncio loop instead of apscheduler — one fewer dependency,
and the interval is the only knob we need.
"""

import asyncio
import signal

from structlog import get_logger

from app.core.logging import setup_logging
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.ingestion.pipeline import run_pipeline

logger = get_logger(__name__)

INTERVAL_SECONDS = 6 * 60 * 60


async def _run_loop() -> None:
    # ponytail: prime data immediately on startup so a fresh deploy isn't empty
    # for up to 6h. One fetch now, then the regular interval.
    async with async_session_factory() as session:
        try:
            result = await run_pipeline(session)
            logger.info("scheduler_initial_ingest", result=result)
        except Exception as e:
            logger.error("scheduler_initial_ingest_failed", error=str(e))
    while True:
        async with async_session_factory() as session:
            try:
                result = await run_pipeline(session)
                logger.info("scheduler_ingest", result=result)
            except Exception as e:  # ponytail: one failed run must not kill the loop
                logger.error("scheduler_ingest_failed", error=str(e))
        await asyncio.sleep(INTERVAL_SECONDS)


def main() -> None:
    setup_logging()
    stop = asyncio.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    logger.info("scheduler_started", interval_hours=6)
    try:
        asyncio.run(_run_loop())
    finally:
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
