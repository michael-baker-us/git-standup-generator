"""Tests for TemplateSummarizer and the categorize() helper."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from standup_generator.models import Commit, StandupReport
from standup_generator.summarizers.template import TemplateSummarizer, categorize

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2026, 6, 26, 9, 0, 0, tzinfo=UTC)
_SINCE = datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC)
_UNTIL = datetime(2026, 6, 26, 9, 0, 0, tzinfo=UTC)


def _commit(subject: str, repo: str = "api", **kwargs: object) -> Commit:
    defaults: dict[str, object] = {
        "sha": "a" * 40,
        "author_name": "Dev",
        "author_email": "dev@example.com",
        "timestamp": _TS,
        "body": "",
        "files_changed": 1,
        "insertions": 10,
        "deletions": 2,
    }
    defaults.update(kwargs)
    return Commit(repo=repo, subject=subject, **defaults)  # type: ignore[arg-type]


def _summarize(commits: list[Commit], author: str | None = None) -> StandupReport:
    return TemplateSummarizer().summarize(commits, since=_SINCE, until=_UNTIL, author=author)


# ---------------------------------------------------------------------------
# categorize() — every row of the mapping table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject, expected",
    [
        ("feat: add login", "Features"),
        ("feat(auth): add refresh-token rotation", "Features"),
        ("feat(ui)!: redesign nav bar", "Features"),
        ("fix: null check on session", "Fixes"),
        ("fix(db): handle timeout", "Fixes"),
        ("perf: cache user lookups", "Performance"),
        ("refactor: extract helper", "Refactors"),
        ("docs: update README", "Docs"),
        ("test: add unit tests", "Tests"),
        ("build: upgrade deps", "Chores"),
        ("ci: add coverage step", "Chores"),
        ("chore: remove dead code", "Chores"),
        ("style: fix lint warnings", "Style"),
        ("revert: undo feat(auth)", "Reverts"),
        # Unknown conventional-commit type → Other
        ("wip: still in progress", "Other"),
        ("merge branch main", "Other"),
        ("Initial commit", "Other"),
        # Empty subject
        ("", "Other"),
    ],
)
def test_categorize(subject: str, expected: str) -> None:
    assert categorize(subject) == expected


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_commits_returns_empty_report() -> None:
    report = _summarize([])
    assert report.is_empty
    assert report.total_commits == 0
    assert report.total_insertions == 0
    assert report.total_deletions == 0
    assert report.repos == ()
    assert report.narrative is None


# ---------------------------------------------------------------------------
# Single repo — grouping and ordering
# ---------------------------------------------------------------------------


def test_group_order_matches_spec() -> None:
    commits = [
        _commit("chore: remove dead code"),
        _commit("fix: null check"),
        _commit("feat: add login"),
        _commit("test: add tests"),
        _commit("docs: update README"),
        _commit("revert: undo fix"),
        _commit("perf: cache lookups"),
        _commit("style: lint"),
        _commit("refactor: extract helper"),
        _commit("ci: add step"),
        _commit("wip: misc"),
    ]
    report = _summarize(commits)
    assert len(report.repos) == 1
    titles = [g.title for g in report.repos[0].groups]
    assert titles == [
        "Features",
        "Fixes",
        "Performance",
        "Refactors",
        "Docs",
        "Tests",
        "Chores",
        "Style",
        "Reverts",
        "Other",
    ]


def test_empty_categories_dropped() -> None:
    commits = [_commit("feat: a"), _commit("fix: b")]
    report = _summarize(commits)
    titles = [g.title for g in report.repos[0].groups]
    assert titles == ["Features", "Fixes"]


def test_chores_group_merges_build_ci_chore() -> None:
    commits = [
        _commit("build: upgrade deps"),
        _commit("ci: add step"),
        _commit("chore: cleanup"),
    ]
    report = _summarize(commits)
    groups = report.repos[0].groups
    assert len(groups) == 1
    assert groups[0].title == "Chores"
    assert len(groups[0].commits) == 3


# ---------------------------------------------------------------------------
# Per-repo aggregation
# ---------------------------------------------------------------------------


def test_per_repo_stats_aggregated() -> None:
    commits = [
        _commit("feat: a", insertions=100, deletions=10, files_changed=3),
        _commit("fix: b", insertions=50, deletions=5, files_changed=2),
    ]
    report = _summarize(commits)
    rs = report.repos[0]
    assert rs.commit_count == 2
    assert rs.insertions == 150
    assert rs.deletions == 15
    assert rs.files_changed == 5


def test_total_stats_aggregated() -> None:
    commits = [
        _commit("feat: a", insertions=100, deletions=10, files_changed=3),
        _commit("fix: b", insertions=50, deletions=5, files_changed=2),
    ]
    report = _summarize(commits)
    assert report.total_commits == 2
    assert report.total_insertions == 150
    assert report.total_deletions == 15


# ---------------------------------------------------------------------------
# Multi-repo ordering
# ---------------------------------------------------------------------------


def test_multi_repo_preserves_first_seen_order() -> None:
    commits = [
        _commit("feat: x", repo="alpha"),
        _commit("fix: y", repo="beta"),
        _commit("docs: z", repo="alpha"),
        _commit("chore: w", repo="gamma"),
    ]
    report = _summarize(commits)
    assert [r.repo for r in report.repos] == ["alpha", "beta", "gamma"]


def test_multi_repo_totals_sum_all_repos() -> None:
    commits = [
        _commit("feat: a", repo="api", insertions=100, deletions=10, files_changed=2),
        _commit("fix: b", repo="web", insertions=50, deletions=5, files_changed=1),
    ]
    report = _summarize(commits)
    assert report.total_commits == 2
    assert report.total_insertions == 150
    assert report.total_deletions == 15
    assert len(report.repos) == 2


def test_multi_repo_per_repo_stats_isolated() -> None:
    commits = [
        _commit("feat: a", repo="api", insertions=200, deletions=20, files_changed=4),
        _commit("fix: b", repo="web", insertions=30, deletions=3, files_changed=1),
    ]
    report = _summarize(commits)
    api = next(r for r in report.repos if r.repo == "api")
    web = next(r for r in report.repos if r.repo == "web")
    assert api.insertions == 200
    assert web.insertions == 30


# ---------------------------------------------------------------------------
# Report metadata
# ---------------------------------------------------------------------------


def test_report_carries_since_until_author() -> None:
    report = _summarize([_commit("feat: x")], author="dev@example.com")
    assert report.since == _SINCE
    assert report.until == _UNTIL
    assert report.author == "dev@example.com"


def test_narrative_is_none() -> None:
    report = _summarize([_commit("feat: x")])
    assert report.narrative is None


def test_repos_with_zero_commits_not_included() -> None:
    # All commits belong to one repo; other repo never appears.
    commits = [_commit("feat: a", repo="only")]
    report = _summarize(commits)
    assert len(report.repos) == 1
    assert report.repos[0].repo == "only"
