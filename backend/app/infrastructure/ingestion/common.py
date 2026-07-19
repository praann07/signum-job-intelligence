"""Shared ingestion helpers used by both the API ingest endpoint and the
pipeline scheduler, so detection/fingerprinting stay consistent everywhere.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Employer


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _fingerprint(title: str, company: str, location: str | None) -> str:
    raw = f"{_norm(title)}|{_norm(company)}|{_norm(location or '')}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_seniority(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("intern", "internship")):
        return "intern"
    if any(w in t for w in ("junior", "jr", "entry")):
        return "junior"
    if any(w in t for w in ("senior", "sr", "lead", "principal", "staff")):
        return "senior"
    if any(w in t for w in ("head", "director", "vp", "chief", "manager")):
        return "lead"
    return "mid"


async def ensure_employer(session: AsyncSession, name: str) -> Employer:
    res = await session.execute(select(Employer).where(Employer.name == name))
    emp = res.scalar_one_or_none()
    if not emp:
        emp = Employer(name=name, size="unknown", industry=None, url=None)
        session.add(emp)
        await session.flush()
    return emp


def parse_posted_at(value: str | None) -> datetime:
    """Parse an ISO timestamp from a source into a timezone-aware datetime."""
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
