"""Breakout signal math — pure, testable functions.

breakout(a,b) = velocity × novelty × log(count + 1)
  velocity = recent_count − prior_count   (acceleration over the window)
  novelty = 1 / (days_since_first_seen + 1)   (recent pairs score higher)
"""

from __future__ import annotations

from datetime import datetime
from math import log


def breakout_score(
    total: int,
    recent: int,
    prior: int,
    first_seen: datetime,
    now: datetime,
) -> float:
    velocity = recent - prior
    days_since = max((now - first_seen).days, 1)
    novelty = 1.0 / (days_since + 1)
    return round(velocity * novelty * log(total + 1), 4)
