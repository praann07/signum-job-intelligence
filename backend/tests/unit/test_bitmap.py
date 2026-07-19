"""Bitmap index unit test.

Uses fakeredis when available (no real Redis needed). Skips if neither
fakeredis nor a reachable Redis is present.
"""

import importlib.util
import uuid

import pytest

from app.infrastructure.indexing.bitmap import BitmapIndex

_HAS_FAKEREDIS = importlib.util.find_spec("fakeredis") is not None


def _make_index(monkeypatch):
    if _HAS_FAKEREDIS:
        import fakeredis.aioredis as fake

        idx = BitmapIndex("redis://fake")
        idx.redis = fake.FakeRedis()
        return idx
    pytest.skip("fakeredis not installed — install it to run bitmap tests")


@pytest.mark.asyncio
async def test_add_and_search_single_skill(monkeypatch):
    idx = _make_index(monkeypatch)
    eid = uuid.uuid4()
    n = await idx.next_index()
    await idx.add_posting(n, eid, ["python", "docker"])
    res = await idx.search(["python"])
    assert len(res) == 1
    assert res[0]["event_id"] == str(eid)


@pytest.mark.asyncio
async def test_multi_filter_and(monkeypatch):
    idx = _make_index(monkeypatch)
    e1 = uuid.uuid4()
    e2 = uuid.uuid4()
    n1 = await idx.next_index()
    await idx.add_posting(n1, e1, ["python", "docker"], seniority="senior", country="in")
    n2 = await idx.next_index()
    await idx.add_posting(n2, e2, ["python"], seniority="junior", country="us")

    both = await idx.search(["python", "docker"])
    assert len(both) == 1
    assert both[0]["event_id"] == str(e1)

    filt = await idx.search(["python"], {"seniority": "senior"})
    assert len(filt) == 1
    assert filt[0]["event_id"] == str(e1)
