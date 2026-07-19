from datetime import UTC, datetime, timedelta

from app.infrastructure.signals import breakout_score


def test_breakout_favors_rising_recent_pairs():
    now = datetime.now(UTC)
    recent = datetime.now(UTC) - timedelta(days=2)
    old = datetime.now(UTC) - timedelta(days=400)

    # Same volume, but the recent-first-seen pair must score higher (novelty).
    rising = breakout_score(total=50, recent=40, prior=10, first_seen=recent, now=now)
    stale = breakout_score(total=50, recent=40, prior=10, first_seen=old, now=now)
    assert rising > stale


def test_breakout_rewards_velocity_not_just_volume():
    now = datetime.now(UTC)
    fs = datetime.now(UTC) - timedelta(days=10)

    # High total but flat (no velocity) should score ~0.
    flat = breakout_score(total=500, recent=250, prior=250, first_seen=fs, now=now)
    # Lower total but accelerating.
    accelerating = breakout_score(total=60, recent=50, prior=10, first_seen=fs, now=now)
    assert accelerating > flat


def test_breakout_zero_when_no_velocity():
    now = datetime.now(UTC)
    fs = datetime.now(UTC) - timedelta(days=10)
    assert breakout_score(total=100, recent=50, prior=50, first_seen=fs, now=now) == 0.0
