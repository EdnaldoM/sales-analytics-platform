"""Generator settings: random seed, time window and volumes.

Reproducibility rule: the same seed, the same anchor date and the same locked
library versions (uv.lock) always produce identical data.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
LOCAL_TZ = ZoneInfo("America/New_York")  # business time zone; CRM and ERP store it (Q8)

DEFAULT_SEED = 42
DEFAULT_ANCHOR_DATE = date(2026, 11, 22)


@dataclass(frozen=True)
class Volumes:
    """Target row counts for the historical load (docs/architecture/source-systems.md, §7)."""

    ecommerce_customers: int = 50_000
    crm_linked_share: float = 0.85  # online customers who also have a CRM record
    crm_leads: int = 4_600  # CRM-only customers who never bought online
    products: int = 2_000


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = DEFAULT_SEED
    anchor_date: date = DEFAULT_ANCHOR_DATE  # last day of the simulated history
    history_months: int = 24
    volumes: Volumes = field(default_factory=Volumes)

    @classmethod
    def from_env(cls, seed: int | None = None, anchor_date: date | None = None) -> GeneratorConfig:
        """Command-line values win over environment variables, which win over defaults."""
        if seed is None:
            seed = int(os.environ.get("GENERATOR_SEED") or DEFAULT_SEED)
        if anchor_date is None:
            raw = os.environ.get("GENERATOR_ANCHOR_DATE")
            anchor_date = date.fromisoformat(raw) if raw else DEFAULT_ANCHOR_DATE
        return cls(seed=seed, anchor_date=anchor_date)

    # -- time window ---------------------------------------------------------

    @property
    def history_start(self) -> date:
        """First day of the simulated history."""
        return subtract_months(self.anchor_date, self.history_months) + timedelta(days=1)

    @property
    def window_start(self) -> datetime:
        """Start of the history: midnight (business time) of the first day."""
        return datetime.combine(self.history_start, time.min, LOCAL_TZ)

    @property
    def window_end(self) -> datetime:
        """End of the history (exclusive): midnight after the anchor date."""
        return datetime.combine(self.anchor_date + timedelta(days=1), time.min, LOCAL_TZ)

    # -- randomness ----------------------------------------------------------

    def rng(self, stream: str) -> random.Random:
        """Independent, reproducible random stream for one part of the data.

        Separate streams keep parts independent: changing how orders are
        generated does not change the customers. A string seed is hashed with
        SHA-512 by `random`, so it is stable across runs and machines (unlike
        Python's built-in hash(), which is randomized per process).
        """
        return random.Random(f"{self.seed}:{stream}")


def subtract_months(day: date, months: int) -> date:
    """Same day `months` earlier (day capped at 28 to stay valid in every month)."""
    year, month_index = divmod(day.year * 12 + (day.month - 1) - months, 12)
    return date(year, month_index + 1, min(day.day, 28))
