"""Tests for timerange.resolve_range — every preset, every relevant weekday."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from standup_generator.timerange import RangePreset, resolve_range

# Fixed reference point: Wednesday 2026-06-24 09:15:00 UTC
WED = datetime(2026, 6, 24, 9, 15, 0, tzinfo=timezone.utc)


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)


class TestToday:
    def test_since_is_start_of_day(self) -> None:
        since, until = resolve_range(RangePreset.TODAY, WED)
        assert since == _dt(2026, 6, 24)
        assert until == WED

    def test_midnight_now_since_equals_now(self) -> None:
        midnight = _dt(2026, 6, 24)
        since, until = resolve_range(RangePreset.TODAY, midnight)
        assert since == midnight
        assert until == midnight


class TestYesterday:
    def test_since_is_previous_day_start(self) -> None:
        since, until = resolve_range(RangePreset.YESTERDAY, WED)
        assert since == _dt(2026, 6, 23)
        assert until == WED

    def test_crosses_month_boundary(self) -> None:
        # 2026-07-01, yesterday should be 2026-06-30
        now = _dt(2026, 7, 1, 10, 0)
        since, _ = resolve_range(RangePreset.YESTERDAY, now)
        assert since == _dt(2026, 6, 30)


class TestWeek:
    def test_since_is_seven_days_back(self) -> None:
        since, until = resolve_range(RangePreset.WEEK, WED)
        assert since == _dt(2026, 6, 17)
        assert until == WED


class TestLastWorkingDay:
    # Monday (weekday 0) → previous Friday
    def test_monday_returns_friday(self) -> None:
        # 2026-06-22 is a Monday
        monday = _dt(2026, 6, 22, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, monday)
        assert since == _dt(2026, 6, 19)  # Friday

    # Tuesday → Monday
    def test_tuesday_returns_monday(self) -> None:
        tuesday = _dt(2026, 6, 23, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, tuesday)
        assert since == _dt(2026, 6, 22)

    # Wednesday → Tuesday
    def test_wednesday_returns_tuesday(self) -> None:
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, WED)
        assert since == _dt(2026, 6, 23)

    # Thursday → Wednesday
    def test_thursday_returns_wednesday(self) -> None:
        thursday = _dt(2026, 6, 25, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, thursday)
        assert since == _dt(2026, 6, 24)

    # Friday → Thursday
    def test_friday_returns_thursday(self) -> None:
        friday = _dt(2026, 6, 26, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, friday)
        assert since == _dt(2026, 6, 25)

    # Saturday → Friday
    def test_saturday_returns_friday(self) -> None:
        saturday = _dt(2026, 6, 27, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, saturday)
        assert since == _dt(2026, 6, 26)

    # Sunday → Friday
    def test_sunday_returns_friday(self) -> None:
        sunday = _dt(2026, 6, 28, 9, 0)
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, sunday)
        assert since == _dt(2026, 6, 26)

    def test_until_is_now(self) -> None:
        _, until = resolve_range(RangePreset.LAST_WORKING_DAY, WED)
        assert until == WED

    def test_since_is_midnight(self) -> None:
        since, _ = resolve_range(RangePreset.LAST_WORKING_DAY, WED)
        assert since.hour == 0
        assert since.minute == 0
        assert since.second == 0
        assert since.microsecond == 0
