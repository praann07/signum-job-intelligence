"""Custom bitmap index over Redis.

Each distinct categorical value (skill, seniority, country, company_size) gets
one Redis bitstring — one bit per posting (its sequential posting number).
A multi-filter AND query is a BITOP AND across the relevant bitstrings, then a
single read of the result. This is O(rows/64) regardless of filter count, which
is why it beats B-tree intersection as filters grow.

Index keys:
  bm:skill:<value>     posting numbers that have this skill
  bm:sen:<value>       seniority filter
  bm:country:<value>   country filter
  bm:size:<value>      company_size filter
  idx:<n>              posting number n -> event_id (string)
"""

from __future__ import annotations

from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

NEXT_KEY = "posting_counter"
RESULT_KEY = "bm:_result"


class BitmapIndex:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=False)

    async def next_index(self) -> int:
        return await self.redis.incr(NEXT_KEY)

    def _key(self, field: str, value: str) -> str:
        return f"bm:{field}:{value}"

    async def add_posting(
        self,
        posting_number: int,
        event_id: UUID,
        skills: list[str],
        seniority: str | None = None,
        country: str | None = None,
        company_size: str | None = None,
        title: str | None = None,
        source: str | None = None,
        url: str | None = None,
    ) -> None:
        pipe = self.redis.pipeline()
        pipe.set(f"idx:{posting_number}", str(event_id))
        # ponytail: stash title/source/url so bitmap search returns full rows
        # without a DB join.
        pipe.hset(f"meta:{posting_number}", mapping={
            "title": title or "", "source": source or "", "url": url or "",
        })
        for s in skills:
            pipe.setbit(self._key("skill", s.lower()), posting_number, 1)
        for field, val in (("sen", seniority), ("country", country), ("size", company_size)):
            if val:
                pipe.setbit(self._key(field, val.lower()), posting_number, 1)
        await pipe.execute()

    async def search(
        self,
        skills: list[str] | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        # Filter dict keys the API uses -> bitmap field codes used at write time.
        field_code: dict[str, str] = {
            "seniority": "sen",
            "country": "country",
            "company_size": "size",
        }
        keys: list[str] = []
        for s in skills or []:
            keys.append(self._key("skill", s.lower()))
        for field, val in (filters or {}).items():
            code = field_code.get(field, field)
            if val:
                keys.append(self._key(code, val.lower()))

        if not keys:
            return []

        if len(keys) == 1:
            result_key = keys[0]
        else:
            result_key = RESULT_KEY
            await self.redis.bitop("AND", result_key, *keys)

        total = await self.redis.bitcount(result_key)
        if total == 0:
            return []

        # ponytail: single GET of the whole result bitmap, then scan bytes locally.
        raw = await self.redis.get(result_key)
        if not raw:
            return []

        out: list[dict[str, object]] = []
        matched_idx: list[int] = []
        for byte_pos, byte in enumerate(raw):
            if byte == 0:
                continue
            for bit in range(8):
                # Redis SETBIT numbers bits MSB-first, so bit `b` in the byte
                # corresponds to posting number (byte_pos*8 + (7 - b)).
                if isinstance(byte, int) and byte & (1 << (7 - bit)):
                    idx = byte_pos * 8 + bit
                    if idx == 0:
                        continue
                    matched_idx.append(idx)
                    if len(matched_idx) >= limit:
                        break

        if not matched_idx:
            return []

        # batched fetch of event id + meta (title/source/url) for the matches.
        pipe = self.redis.pipeline()
        for idx in matched_idx:
            pipe.get(f"idx:{idx}")
            pipe.hmget(f"meta:{idx}", "title", "source", "url")
        vals = await pipe.execute()

        def _dec(v: bytes | str | None) -> str:
            if not v:
                return ""
            return v.decode() if isinstance(v, bytes) else v

        for i, idx in enumerate(matched_idx):
            eid = vals[i * 2]
            meta = vals[i * 2 + 1]
            if not eid:
                continue
            out.append({
                "event_id": eid.decode() if isinstance(eid, bytes) else eid,
                "index": idx,
                "title": _dec(meta[0]),
                "source": _dec(meta[1]),
                "url": _dec(meta[2]),
            })
        return out

    async def rebuild_from_db(self, session: AsyncSession) -> int:
        """Rebuild the entire bitmap index from job_events + job_skills.

        ponytail: if Redis loses its data (no AOF/persistence), the index is
        silently empty and search returns nothing. Call this on startup (and
        after a Redis restart) to reconstruct it from the source of truth (DB).
        Returns the number of postings rebuilt.
        """
        from sqlalchemy import text


        # ponytail: clear existing bitmap keys first so a partial rebuild can't
        # leave stale bits behind.
        for pat in ("bm:*", "idx:*", "meta:*", "posting_counter"):
            keys = await self.redis.keys(pat)
            if keys:
                await self.redis.delete(*keys)

        rows = await session.execute(
            text(
                """
                SELECT e.event_id, e.title, e.source, e.url, e.seniority,
                       e.country, em.size, js.skill
                FROM job_events e
                LEFT JOIN employers em ON em.company_id = e.company_id
                JOIN job_skills js ON js.event_id = e.event_id
                ORDER BY e.posted_at, e.event_id
                """
            )
        )
        events: dict[str, dict[str, object]] = {}
        skills_by_event: dict[str, list[object]] = {}
        for r in rows:
            eid = str(r[0])
            if eid not in events:
                events[eid] = {
                    "title": r[1],
                    "source": r[2],
                    "url": r[3],
                    "seniority": r[4],
                    "country": r[5],
                    "size": r[6],
                }
                skills_by_event[eid] = []
            skills_by_event[eid].append(r[7])

        count = 0
        for eid, data in events.items():
            skills = skills_by_event[eid]
            n = await self.next_index()
            await self.add_posting(
                n,
                _uuid(eid),
                [str(s) for s in skills],
                seniority=str(data["seniority"]) if data["seniority"] else None,
                country=(
                    str(data["country"])
                    if data["country"] not in (None, "unknown", "remote", "eu")
                    else None
                ),
                company_size=str(data["size"]) if data["size"] not in (None, "unknown") else None,
                title=str(data["title"]) if data["title"] else None,
                source=str(data["source"]) if data["source"] else None,
                url=str(data["url"]) if data["url"] else None,
            )
            count += 1
        return count


def _uuid(eid: str) -> UUID:
    from uuid import UUID

    return UUID(eid)
