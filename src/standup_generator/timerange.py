"""Time range resolution from presets."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum


class RangePreset(StrEnum):
    LAST_WORKING_DAY = "last-working-day"
    YESTERDAY = "yesterday"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"


def _start_of_day(dt: datetime) -> datetime:
    """Return midnight at the start of `dt`'s calendar day, in `dt`'s tzinfo."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def resolve_range(preset: RangePreset, now: datetime) -> tuple[datetime, datetime]:
    """Return (since, until) as tz-aware datetimes. `until` is always `now`."""
    until = now

    if preset is RangePreset.TODAY:
        since = _start_of_day(now)

    elif preset is RangePreset.YESTERDAY:
        since = _start_of_day(now - timedelta(days=1))

    elif preset is RangePreset.WEEK:
        since = _start_of_day(now - timedelta(days=7))

    elif preset is RangePreset.MONTH:
        since = _start_of_day(now - timedelta(days=30))

    elif preset is RangePreset.QUARTER:
        since = _start_of_day(now - timedelta(days=90))

    else:  # LAST_WORKING_DAY
        weekday = now.weekday()  # Mon=0 … Sun=6
        if weekday == 0:  # Monday → previous Friday
            delta = 3
        elif weekday == 6:  # Sunday → previous Friday
            delta = 2
        elif weekday == 5:  # Saturday → previous Friday
            delta = 1
        else:  # Tue–Fri → previous calendar day
            delta = 1
        since = _start_of_day(now - timedelta(days=delta))

    return since, until
