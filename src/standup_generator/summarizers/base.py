from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from standup_generator.models import Commit, StandupReport


class Summarizer(Protocol):
    def summarize(
        self,
        commits: Sequence[Commit],
        *,
        since: datetime,
        until: datetime,
        author: str | None,
    ) -> StandupReport: ...
