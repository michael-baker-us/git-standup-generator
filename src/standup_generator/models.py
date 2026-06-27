"""Domain models — all frozen dataclasses, no behavior beyond derived properties."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Commit:
    repo: str
    sha: str
    author_name: str
    author_email: str
    timestamp: datetime  # tz-aware, authored date
    subject: str
    body: str
    files_changed: int
    insertions: int
    deletions: int

    @property
    def short_sha(self) -> str:
        return self.sha[:8]


@dataclass(frozen=True, slots=True)
class CategoryGroup:
    title: str
    commits: tuple[Commit, ...]


@dataclass(frozen=True, slots=True)
class RepoSummary:
    repo: str
    groups: tuple[CategoryGroup, ...]
    commit_count: int
    insertions: int
    deletions: int
    files_changed: int


@dataclass(frozen=True, slots=True)
class StandupReport:
    since: datetime
    until: datetime
    author: str | None
    repos: tuple[RepoSummary, ...]
    total_commits: int
    total_insertions: int
    total_deletions: int
    # Reserved for AI milestone; always None in the template summarizer.
    narrative: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.total_commits == 0
