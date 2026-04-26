from __future__ import annotations

import enum
from collections.abc import Sequence


class MinutesMode(str, enum.Enum):
    """Allowed minute hand positions (minute values 0-59)."""

    exact = "exact"  # only :00
    half = "half"  # :00 and :30
    quarter = "quarter"  # quarter hours: 0, 15, 30, 45
    fives = "fives"  # any multiple of 5

    @classmethod
    def from_str(cls, value: str) -> MinutesMode:
        v = (value or "").strip().lower()
        return cls(v)


def allowed_minutes(mode: MinutesMode) -> list[int]:
    if mode is MinutesMode.exact:
        return [0]
    if mode is MinutesMode.half:
        return [0, 30]
    if mode is MinutesMode.quarter:
        return [0, 15, 30, 45]
    if mode is MinutesMode.fives:
        return list(range(0, 60, 5))
    raise ValueError(f"Unknown mode: {mode}")


def parse_minutes_arg(value: str) -> Sequence[int]:
    return allowed_minutes(MinutesMode.from_str(value))
