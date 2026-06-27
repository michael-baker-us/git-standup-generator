from __future__ import annotations

from datetime import datetime

from standup_generator.models import StandupReport


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def fmt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def empty_line(report: StandupReport) -> str:
    since_str = fmt_datetime(report.since)
    until_str = fmt_datetime(report.until)
    if report.author:
        return (
            f"No commits found for {report.author} between {since_str} and {until_str}."
        )
    return f"No commits found between {since_str} and {until_str}."
