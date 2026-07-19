"""Real ingestion sources for Signum.

Each source yields raw postings from a LIVE endpoint (no synthetic data).
Sources are free and key-less except Naukri (Firecrawl, optional).
"""

from __future__ import annotations

import ast
import datetime as _dt
import re

import httpx
from pydantic import BaseModel


class RawPosting(BaseModel):
    model_config = {"extra": "ignore"}
    title: str
    company: str
    location: str | None = None
    country: str = "unknown"
    tags: list[str] = []
    description: str = ""
    url: str | None = None
    source: str = "unknown"  # provenance: which live API this came from
    posted_at: str | None = None  # ISO string


async def fetch_remotive() -> list[RawPosting]:
    """Remotive public remote-jobs API — real, live, no key."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://remotive.com/api/remote-jobs?search=&category=")
        r.raise_for_status()
        data = r.json().get("jobs", [])
    out = []
    for j in data:
        raw_tags = j.get("tags") or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = ast.literal_eval(raw_tags)
            except (ValueError, SyntaxError):
                raw_tags = [t.strip("'\" ") for t in raw_tags.strip("[]").split(",") if t.strip()]
        out.append(
            RawPosting(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=j.get("candidate_location") or "Remote",
                country="remote",
                tags=[t for t in raw_tags if t],
                description=(j.get("description") or "")[:4000],
                url=j.get("url"),
                source="Remotive",
                posted_at=j.get("publication_date"),
            )
        )
    return out


async def fetch_arbeitnow() -> list[RawPosting]:
    """Arbeitnow public job-board API — real, live, no key (EU/remote heavy)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://www.arbeitnow.com/api/job-board-api")
        r.raise_for_status()
        data = r.json().get("data", [])
    out = []
    for j in data:
        # Arbeitnow has no tags and returns created_at as a unix timestamp.
        ca = j.get("created_at")
        if isinstance(ca, (int, float)):
            ca = _dt.datetime.fromtimestamp(ca, tz=_dt.UTC).isoformat()
        out.append(
            RawPosting(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=j.get("location") or "Remote",
                country="eu",
                tags=[],
                description=(j.get("description") or "")[:4000],
                url=j.get("url"),
                source="Arbeitnow",
                posted_at=ca,
            )
        )
    return out


async def fetch_naukri(
    firecrawl_api_key: str, query: str = "software engineer"
) -> list[RawPosting]:
    """India-specific source via Firecrawl (requires key).

    Falls back to empty list (with a logged warning) when no key is set so the
    pipeline still runs on the key-less sources.
    """
    if not firecrawl_api_key:
        return []
    url = f"https://www.naukri.com/{query.replace(' ', '-')}-jobs"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.firecrawl.dev/v1/scrape",
            json={"url": url, "formats": ["markdown"]},
            headers={"Authorization": f"Bearer {firecrawl_api_key}"},
        )
        r.raise_for_status()
        md = r.json().get("data", {}).get("markdown", "")
    # ponytail: Firecrawl returns raw markdown; split on job-title-like lines.
    # This is a best-effort parse — real structured Naukri API is paid.
    out = []
    for line in md.splitlines():
        if any(k in line.lower() for k in ("experience", "years", "salary", "key skills")):
            title = line.strip().split("|")[0][:120]
            if title:
                out.append(
                    RawPosting(
                        title=title, company="unknown",
                        location="India", country="IN", source="Naukri",
                    )
                )
    return out


# ponytail: HN "Who is Hiring" comments are free-text. We pull a title from the
# first line (before a pipe/location marker) and a company from the start. This
# is heuristic but the description text carries the real skill signal for NER.
_TITLE_RE = re.compile(r"^([^|<(]{4,80}?)\s*(?:[|]\s*|\bat\b\s*|\bin\b\s*|\s[-–]\s*).*", re.I)


async def fetch_hackernews(limit: int = 200) -> list[RawPosting]:
    """Hacker News "Who is Hiring" comments via the key-less Algolia API.

    Each comment is one job posting. We keep the raw comment text as the
    description (NER extracts skills from it) and derive a title heuristically.
    """
    out: list[RawPosting] = []
    async with httpx.AsyncClient(timeout=30) as c:
        # ponytail: sort by date, grab recent hiring comments in bulk pages.
        for page in range(0, (limit // 100) + 1):
            r = await c.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "tags": "comment",
                    "query": "hiring",
                    "hitsPerPage": 100,
                    "page": page,
                },
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if not hits:
                break
            for h in hits:
                text = (h.get("comment_text") or "").strip()
                if not text or len(text) < 30:
                    continue
                # strip HTML tags for clean text
                clean = re.sub(r"<[^>]+>", " ", text)
                clean = re.sub(r"\s+", " ", clean).strip()
                # title = first sentence-ish chunk, else first 80 chars
                first_line = clean.split(". ")[0][:80]
                m = _TITLE_RE.match(clean)
                title = (m.group(1).strip() if m else first_line) or "Hacker News posting"
                out.append(
                    RawPosting(
                        title=title[:120],
                        company=title.split("|")[0][:60] if "|" in title else "unknown",
                        location="Remote" if "remote" in clean.lower() else "US",
                        country="us",
                        tags=[],
                        description=clean[:4000],
                        url=(
                            "https://news.ycombinator.com/item?id="
                            + str(h.get("story_id") or h.get("objectID"))
                        ),
                        source="HackerNews",
                        posted_at=h.get("created_at"),
                    )
                )
                if len(out) >= limit:
                    return out
    return out

