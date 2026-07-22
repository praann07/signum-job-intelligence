import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import create_app

settings = get_settings()


@pytest.fixture
async def db_engine():
    # ponytail: function-scoped so the engine lives in the same event loop as
    # the test (pytest-asyncio spins a fresh loop per test). Tests run against
    # the already-migrated dev DB; clean_db truncates per test.
    engine = create_async_engine(settings.database_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_db(db_engine):
    """Truncate all tables before each test so integration tests start clean."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE job_skills, job_events, employers, "
                "skill_cooccurrence, emerging_candidates "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest.fixture(autouse=True)
def reset_singletons():
    """Clear cached Redis/engine loop bindings so they rebind to the test loop.

    ponytail: get_redis()/get_engine() + the BitmapIndex module singletons cache
    per event loop; pytest-asyncio runs each test in its own loop, so we clear
    them before each test to force recreation in the new loop (avoids the
    "attached to a different loop" / "Event loop is closed" errors).
    """
    import app.api.v1.ingest as ingest_mod
    import app.api.v1.search as search_mod
    import app.infrastructure.cache.redis as redis_mod
    from app.infrastructure.database import session as session_mod

    session_mod._engine = None
    session_mod._engine_loop = None
    redis_mod._redis = None
    redis_mod._redis_loop = None
    ingest_mod._bm = None
    search_mod._index = None
    yield


@pytest.fixture
async def client(db_session):
    from app.api.deps import get_session

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def api_client(client):
    return client
