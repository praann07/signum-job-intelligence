from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from structlog import get_logger

from app.api.errors import general_error_handler
from app.api.middleware import AuthMiddleware, RateLimitMiddleware, RequestLoggingMiddleware
from app.api.v1.emerging import router as emerging_router
from app.api.v1.extract import router as extract_router
from app.api.v1.graph import router as graph_router
from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.search import router as search_router
from app.api.v1.signals import router as signals_router
from app.api.v1.taxonomy import router as taxonomy_router
from app.api.v1.trends import router as trends_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.cache.redis import close_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    # ponytail: rebuild the bitmap index from the DB if Redis came up empty
    # (no persistence / restart). Search must never silently return nothing.
    try:
        from sqlalchemy import text

        from app.infrastructure.database.session import async_session_factory
        from app.infrastructure.indexing.bitmap import BitmapIndex

        async with async_session_factory() as session:
            db_count = await session.execute(text("SELECT COUNT(*) FROM job_events"))
            total = db_count.scalar() or 0
            bm = BitmapIndex(get_settings().redis_url)
            counter = await bm.redis.get("posting_counter")
            if not counter and total > 0:
                rebuilt = await bm.rebuild_from_db(session)
                logger.info("bitmap_rebuilt_from_db", postings=rebuilt)
    except Exception as e:  # ponytail: never block startup on a rebuild failure
        logger.warning("bitmap_rebuild_skipped", error=str(e))
    yield
    await close_redis()


def create_app() -> FastAPI:  # noqa: D103
    settings = get_settings()

    app = FastAPI(
        title="Signum API",
        description="Real-time job market intelligence system",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ponytail: disable browser caching for the dashboard so edits show up
    # immediately instead of serving a stale ETag/Last-Modified copy.
    @app.middleware("http")
    async def no_cache_dashboard(request: Request, call_next: Callable[[Request], Any]) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/dashboard"):
            response.headers.update(
                {
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                }
            )
        return response  # type: ignore[no-any-return]

    app.include_router(health_router, prefix="/api/v1", tags=["system"])
    app.include_router(ingest_router, prefix="/api/v1", tags=["ingestion"])
    app.include_router(extract_router, prefix="/api/v1", tags=["extraction"])
    app.include_router(emerging_router, prefix="/api/v1", tags=["extraction"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(signals_router, prefix="/api/v1", tags=["signals"])
    app.include_router(taxonomy_router, prefix="/api/v1", tags=["taxonomy"])
    app.include_router(graph_router, prefix="/api/v1", tags=["graph"])
    app.include_router(pipeline_router, prefix="/api/v1", tags=["ingestion"])
    app.include_router(trends_router, prefix="/api/v1", tags=["trends"])
    app.include_router(metrics_router, prefix="/api/v1", tags=["monitoring"])

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(static_dir), html=True),
            name="dashboard",
        )
        graph_dir = static_dir / "graph"
        if graph_dir.exists():
            app.mount(
                "/graph",
                StaticFiles(directory=str(graph_dir), html=True),
                name="graph",
            )

    @app.get("/")
    async def root() -> Response:
        return RedirectResponse(url="/dashboard/")

    app.add_exception_handler(Exception, general_error_handler)

    return app


app = create_app()
