"""Time helpers.

Inside the generator every moment is a timezone-aware datetime. Conversion to
each system's storage convention happens only when a row is built:
e-commerce stores UTC, CRM and ERP store local time without a time zone (Q8).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from data_generator.config import LOCAL_TZ, UTC


def random_between(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """Random moment in [start, end), with one-second resolution."""
    seconds = int((end - start).total_seconds())
    if seconds <= 0:
        return start
    return start + timedelta(seconds=rng.randrange(seconds))


def as_utc(moment: datetime) -> datetime:
    """E-commerce convention: timestamptz, normalized to UTC."""
    return moment.astimezone(UTC)


def as_local_naive(moment: datetime) -> datetime:
    """CRM/ERP convention: America/New_York wall-clock time, time zone dropped."""
    return moment.astimezone(LOCAL_TZ).replace(tzinfo=None)
