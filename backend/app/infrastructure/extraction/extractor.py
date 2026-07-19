"""Skill extraction over REAL posting text.

Stage 1: exact + alias match against the curated taxonomy (high precision).
Stage 2: noun-chunk NER to surface candidate emerging skills not yet known.
"""

from __future__ import annotations

import re
import time
from difflib import SequenceMatcher

import spacy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import SkillTaxonomy

_nlp: spacy.language.Language | None = None
_TAXONOMY_CACHE: tuple[dict[str, str], dict[str, set[str]]] | None = None
_TAXONOMY_CACHE_TS: float = 0.0
_TAXONOMY_TTL = 300  # seconds

_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+#.]{1,29}$")


# ponytail: common non-skill noise chunks to drop from Stage 2
_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "for",
    "with", "to", "in", "on", "at", "by", "from", "as", "into", "onto", "than",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "we", "you", "your", "our", "us", "he", "she", "his", "her", "i", "me", "my",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "can", "could", "should", "may", "might",
    "need", "needs", "required", "use", "using", "used", "plus", "nice", "good",
    "want", "like", "help", "work", "working", "looking", "join", "make", "get",
    "years", "year", "experience", "role", "team", "day", "company", "job",
    "responsibilities", "requirements", "skills", "ability", "knowledge",
    "qualification", "qualifications", "summary", "overview", "about", "what",
    "who", "why", "how", "when", "where", "ul", "li", "br", "http", "https",
    "com", "www", "email", "phone", "location", "remote", "full", "time", "part",
    "new", "one", "two", "per", "all", "any", "some", "more", "most", "other",
    "them", "part", "candidates", "candidate", "home", "services", "service",
    "demand", "quality", "bookings", "annual", "month", "months", "week", "day",
    "days", "today", "now", "first", "last", "next", "each", "both", "such",
    "same", "well", "also", "still", "much", "many", "few", "lot", "things",
}


def _get_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        # ponytail: lazy-load so import (and test collection) doesn't block on
        # the ~2s spaCy model load.
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


async def _load_taxonomy(session: AsyncSession) -> tuple[dict[str, str], dict[str, set[str]]]:
    global _TAXONOMY_CACHE, _TAXONOMY_CACHE_TS
    now = time.monotonic()
    if _TAXONOMY_CACHE is not None and (now - _TAXONOMY_CACHE_TS) < _TAXONOMY_TTL:
        return _TAXONOMY_CACHE

    rows = await session.execute(select(SkillTaxonomy).where(SkillTaxonomy.is_active))
    alias_map: dict[str, set[str]] = {}
    norm_map: dict[str, str] = {}
    for t in rows.scalars().all():
        key = t.skill.strip().lower()
        norm_map[key] = t.skill
        aliases = set(a.strip().lower() for a in (t.aliases or []))
        aliases.add(key)
        alias_map[t.skill] = aliases

    _TAXONOMY_CACHE = (norm_map, alias_map)
    _TAXONOMY_CACHE_TS = now
    return _TAXONOMY_CACHE


def extract_known(
    text: str, norm_map: dict[str, str], alias_map: dict[str, set[str]]
) -> list[dict[str, object]]:
    doc = _get_nlp()(text)
    present: set[str] = set()
    for tok in doc:
        if _TOKEN_RE.match(tok.text):
            present.add(tok.text.lower())
    for chunk in doc.noun_chunks:
        c = chunk.text.strip().lower()
        if 2 <= len(c.split()) <= 3 and _TOKEN_RE.match(c.replace(" ", "x")) is None:
            present.add(c)

    results: list[dict[str, object]] = []
    for canonical, aliases in alias_map.items():
        if present & aliases:
            results.append({"skill": canonical, "is_known": True, "extraction_confidence": 0.99})
        else:
            best = max((_similar(a, p) for a in aliases for p in present), default=0.0)
            if best >= 0.9:
                results.append(
                    {"skill": canonical, "is_known": True, "extraction_confidence": round(best, 2)}
                )
    return results


def discover_emerging(text: str, norm_map: dict[str, str]) -> list[str]:  # noqa: D103
    """Stage 2: noun chunks not matching any known skill -> candidate emerging."""
    doc = _get_nlp()(text)
    found: set[str] = set()
    for chunk in doc.noun_chunks:
        c = chunk.text.strip().lower()
        toks = c.split()
        if not (1 <= len(toks) <= 3):
            continue
        if any(t in _STOP or len(t) < 2 for t in toks):
            continue
        if not all(_TOKEN_RE.match(t) for t in toks):
            continue
        if c in norm_map:
            continue
        found.add(c)
    return sorted(found)


async def extract_from_text(
    session: AsyncSession, title: str, description: str
) -> tuple[list[dict[str, object]], list[str]]:
    norm_map, alias_map = await _load_taxonomy(session)
    known = extract_known(f"{title}\n{description}", norm_map, alias_map)
    emerging = discover_emerging(f"{title}\n{description}", norm_map)
    return known, emerging
