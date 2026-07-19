from asyncio import get_running_loop
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

_engine: Optional[AsyncEngine] = None
_engine_loop: Optional[object] = None


def get_engine() -> AsyncEngine:
    """Return an async engine bound to the current event loop.

    ponytail: pytest-asyncio creates a fresh loop per test; a module-level
    engine would be stuck on the first (closed) loop. We recreate the engine
    when the loop changes. Cheap, and keeps tests from hitting closed loops.
    """
    global _engine, _engine_loop
    loop = get_running_loop()
    if _engine is None or _engine_loop is not loop:
        _engine = create_async_engine(
            _settings.database_url, echo=_settings.log_level == "DEBUG"
        )
        _engine_loop = loop
    return _engine


def make_session() -> AsyncSession:
    """Create a session bound to the engine for the current event loop."""
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)()


async_session_factory = make_session
