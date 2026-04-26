"""Angles for a simplified 12-hour analog clock (first-grade model)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClockTime:
    """Hour 1-12, minute 0-59 (minute is one of the allowed set from mode)."""

    hour: int
    minute: int

    def __post_init__(self) -> None:
        if not 1 <= self.hour <= 12:
            raise ValueError("hour must be 1-12")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute must be 0-59")


def minute_hand_angle_radians(minute: int) -> float:
    """0 at 12:00, clockwise. Same convention as trigonometry below."""
    return 2.0 * math.pi * (minute / 60.0)


def hour_hand_angle_radians(hour: int, minute: int) -> float:
    """
    If minutes == 0, hour hand on the exact hour.
    Otherwise, hour hand at the midpoint between this hour and the next (simplified).
    """
    if minute == 0:
        h = 0 if hour == 12 else hour
        return 2.0 * math.pi * (h / 12.0)
    return 2.0 * math.pi * ((hour % 12) + 0.5) / 12.0
