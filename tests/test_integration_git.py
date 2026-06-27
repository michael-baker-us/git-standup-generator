"""Integration tests: real git subprocess, real collector + summarizer + renderers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conftest import make_git_repo
from standup_generator.git.collector import collect_commits
from standup_generator.git.runner import subprocess_runner
from standup_generator.renderers.markdown import MarkdownRenderer
from standup_generator.renderers.text import TextRenderer
from standup_generator.summarizers.template import TemplateSummarizer

_THREE_COMMITS = [
    ("login.py", "feat: add login endpoint"),
    ("parser.py", "fix: resolve null pointer in parser"),
    ("test_parser.py", "test: add unit tests for parser"),
]


@pytest.mark.integration
def test_integration_collect_text_render(tmp_path: Path) -> None:
    """Real repo → collect → summarize → TextRenderer produces expected output."""
    make_git_repo(tmp_path, _THREE_COMMITS)

    now = datetime.now(UTC).astimezone()
    since = now - timedelta(minutes=5)

    commits = collect_commits(
        tmp_path,
        since=since,
        until=now,
        author=None,
        include_merges=False,
        runner=subprocess_runner,
    )

    assert len(commits) == 3
    subjects = {c.subject for c in commits}
    assert "feat: add login endpoint" in subjects
    assert "fix: resolve null pointer in parser" in subjects
    assert "test: add unit tests for parser" in subjects

    report = TemplateSummarizer().summarize(commits, since=since, until=now, author=None)
    assert report.total_commits == 3
    assert not report.is_empty

    repo_summary = report.repos[0]
    group_titles = {g.title for g in repo_summary.groups}
    assert "Features" in group_titles
    assert "Fixes" in group_titles
    assert "Tests" in group_titles

    output = TextRenderer().render(report)
    assert "feat: add login endpoint" in output
    assert "fix: resolve null pointer in parser" in output
    assert "test: add unit tests for parser" in output


@pytest.mark.integration
def test_integration_markdown_render(tmp_path: Path) -> None:
    """Real repo → collect → summarize → MarkdownRenderer produces markdown."""
    make_git_repo(tmp_path, _THREE_COMMITS)

    now = datetime.now(UTC).astimezone()
    since = now - timedelta(minutes=5)

    commits = collect_commits(
        tmp_path,
        since=since,
        until=now,
        author=None,
        include_merges=False,
        runner=subprocess_runner,
    )

    report = TemplateSummarizer().summarize(commits, since=since, until=now, author=None)
    output = MarkdownRenderer().render(report)

    assert output.startswith("# Standup")
    assert "feat: add login endpoint" in output
    assert "### Features" in output
    assert "### Fixes" in output


@pytest.mark.integration
def test_integration_empty_window(tmp_path: Path) -> None:
    """Commits outside the time window produce an empty report."""
    make_git_repo(tmp_path, _THREE_COMMITS)

    now = datetime.now(UTC).astimezone()
    # Window is entirely in the future — no commits can match.
    since = now + timedelta(hours=1)
    until = now + timedelta(hours=2)

    commits = collect_commits(
        tmp_path,
        since=since,
        until=until,
        author=None,
        include_merges=False,
        runner=subprocess_runner,
    )

    assert commits == []
    report = TemplateSummarizer().summarize(commits, since=since, until=until, author=None)
    assert report.is_empty
    assert "No commits found" in TextRenderer().render(report)
