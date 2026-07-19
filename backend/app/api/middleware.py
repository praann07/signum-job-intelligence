import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.infrastructure.cache.redis import get_redis

logger = structlog.get_logger()
counters: dict[str, int] = defaultdict(int)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        if request.method in ("POST", "PUT", "DELETE"):
            auth = request.headers.get("Authorization", "")
            expected = get_settings().api_key
            if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ") != expected:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Missing or invalid API key",
                        "hint": "Send header: Authorization: Bearer <API_KEY>",
                    },
                )
        return await call_next(request)  # type: ignore[no-any-return]


class RateLimitMiddleware(BaseHTTPMiddleware):
    # Per-method limits: GET is read-heavy (higher cap), writes are stricter.
    LIMITS: dict[str, tuple[int, int]] = {
        "GET": (200, 60),
        "POST": (50, 60),
        "PUT": (50, 60),
        "DELETE": (20, 60),
    }

    def __init__(self, app: Any) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        method = request.method
        limit, window = self.LIMITS.get(method, (50, 60))
        client_ip = request.client.host if request.client else "unknown"
        try:
            redis = await get_redis()
            key = f"ratelimit:{method}:{client_ip}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "hint": (
                            f"Max {limit} {method} requests per {window}s. "
                            "Try again later."
                        ),
                    },
                )
        except Exception:
            # ponytail: Redis down — skip rate limiting rather than block traffic
            pass
        return await call_next(request)  # type: ignore[no-any-return]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        counters[request.method] += 1
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000),
        )
        return response  # type: ignore[no-any-return]
