"""Tests for ClaudeSummarizer — uses a fake Anthropic client; no real API calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from standup_generator.models import Commit
from standup_generator.summarizers.claude import ClaudeSummarizer, _build_prompt

# ── Fixtures ──────────────────────────────────────────────────────────────────

_SINCE = datetime(2026, 6, 20, 0, 0, 0, tzinfo=UTC)
_UNTIL = datetime(2026, 6, 27, 9, 0, 0, tzinfo=UTC)


def _commit(subject: str, repo: str = "myrepo", body: str = "") -> Commit:
    return Commit(
        repo=repo,
        sha="abc1234500000000",
        author_name="Dev",
        author_email="dev@example.com",
        timestamp=_SINCE,
        subject=subject,
        body=body,
        files_changed=2,
        insertions=10,
        deletions=3,
    )


def _fake_client(narrative: str) -> Any:
    """Return a minimal mock that looks like anthropic.Anthropic."""
    block = MagicMock()
    block.type = "text"
    block.text = narrative

    message = MagicMock()
    message.content = [block]

    client = MagicMock()
    client.messages.create.return_value = message
    return client


# ── _build_prompt ─────────────────────────────────────────────────────────────


class TestBuildPrompt:
    def test_contains_repo_name(self) -> None:
        commits = [_commit("feat: add login")]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author="dev@example.com"
        )
        prompt = _build_prompt(report)
        assert "myrepo" in prompt

    def test_contains_commit_subject(self) -> None:
        commits = [_commit("fix: resolve race condition")]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author=None
        )
        prompt = _build_prompt(report)
        assert "fix: resolve race condition" in prompt

    def test_includes_commit_body_when_present(self) -> None:
        commits = [_commit("feat: new thing", body="This is the body detail")]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author=None
        )
        prompt = _build_prompt(report)
        assert "This is the body detail" in prompt

    def test_truncates_long_body(self) -> None:
        long_body = "x" * 200
        commits = [_commit("feat: thing", body=long_body)]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author=None
        )
        prompt = _build_prompt(report)
        # Body should appear truncated to 120 chars
        assert "x" * 120 in prompt
        assert "x" * 121 not in prompt

    def test_author_line_when_set(self) -> None:
        commits = [_commit("feat: thing")]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author="alice@example.com"
        )
        prompt = _build_prompt(report)
        assert "alice@example.com" in prompt

    def test_all_authors_line_when_no_author(self) -> None:
        commits = [_commit("feat: thing")]
        report = ClaudeSummarizer(client=_fake_client("x")).summarize(
            commits, since=_SINCE, until=_UNTIL, author=None
        )
        prompt = _build_prompt(report)
        assert "all contributors" in prompt


# ── ClaudeSummarizer.summarize ────────────────────────────────────────────────


class TestClaudeSummarizer:
    def test_narrative_set_on_report(self) -> None:
        commits = [_commit("feat: add login")]
        summarizer = ClaudeSummarizer(client=_fake_client("I added login support."))
        report = summarizer.summarize(commits, since=_SINCE, until=_UNTIL, author=None)
        assert report.narrative == "I added login support."

    def test_narrative_stripped(self) -> None:
        commits = [_commit("fix: bug")]
        summarizer = ClaudeSummarizer(client=_fake_client("  Fixed a bug.  \n"))
        report = summarizer.summarize(commits, since=_SINCE, until=_UNTIL, author=None)
        assert report.narrative == "Fixed a bug."

    def test_empty_commits_returns_no_narrative(self) -> None:
        client = _fake_client("should not be called")
        summarizer = ClaudeSummarizer(client=client)
        report = summarizer.summarize([], since=_SINCE, until=_UNTIL, author=None)
        assert report.narrative is None
        client.messages.create.assert_not_called()

    def test_passes_model_to_api(self) -> None:
        client = _fake_client("ok")
        summarizer = ClaudeSummarizer(model="claude-sonnet-4-6", client=client)
        summarizer.summarize([_commit("feat: x")], since=_SINCE, until=_UNTIL, author=None)
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_structured_data_still_present(self) -> None:
        """The template-built structure (groups, stats) survives the AI enrichment."""
        commits = [_commit("feat: add search"), _commit("fix: crash on empty")]
        summarizer = ClaudeSummarizer(client=_fake_client("Did some work."))
        report = summarizer.summarize(commits, since=_SINCE, until=_UNTIL, author=None)
        assert report.total_commits == 2
        assert len(report.repos) == 1
        assert any(g.title == "Features" for g in report.repos[0].groups)
        assert any(g.title == "Fixes" for g in report.repos[0].groups)

    def test_missing_anthropic_raises_standup_error(self) -> None:
        """If anthropic is not installed, StandupError is raised with install hint."""
        import sys

        summarizer = ClaudeSummarizer()  # no injected client → will try to import
        real_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = None  # type: ignore[assignment]
        try:
            from standup_generator.errors import StandupError

            with pytest.raises(StandupError, match="pip install"):
                summarizer.summarize([_commit("feat: x")], since=_SINCE, until=_UNTIL, author=None)
        finally:
            if real_anthropic is not None:
                sys.modules["anthropic"] = real_anthropic
            else:
                del sys.modules["anthropic"]

    def test_missing_api_key_raises_standup_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing ANTHROPIC_API_KEY gives a clear StandupError, not a raw SDK exception."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from standup_generator.errors import StandupError

        summarizer = ClaudeSummarizer()  # no injected client
        with pytest.raises(StandupError, match="ANTHROPIC_API_KEY"):
            summarizer.summarize([_commit("feat: x")], since=_SINCE, until=_UNTIL, author=None)
