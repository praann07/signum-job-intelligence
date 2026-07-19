from asyncio import get_running_loop

from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings

_redis: AsyncRedis | None = None
_redis_loop = None


async def get_redis() -> AsyncRedis:
    global _redis, _redis_loop
    # ponytail: recreate the client if the event loop changed (e.g. pytest-asyncio
    # spins a fresh loop per test) so we never use a connection bound to a closed
    # loop. Connection recreation is cheap and avoids "Event loop is closed".
    loop = get_running_loop()
    if _redis is None or _redis_loop is not loop:
        if _redis is not None:
            await _redis.aclose()
        _redis = AsyncRedis.from_url(get_settings().redis_url, decode_responses=False)
        _redis_loop = loop
    return _redis


async def close_redis() -> None:
    global _redis, _redis_loop
    if _redis:
        await _redis.aclose()
        _redis = None
        _redis_loop = None
