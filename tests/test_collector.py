"""Tests for git/collector.py — uses fake runners, no real git subprocess."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from standup_generator.errors import GitCommandError, NotAGitRepositoryError
from standup_generator.git.collector import _split_body_and_numstat, _sum_numstat, collect_commits
from standup_generator.git.runner import GitRunner

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_fake_runner(log_output: str) -> GitRunner:
    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            return "true\n"
        if args[0] == "log":
            return log_output
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner


def _make_failing_revparse_runner() -> GitRunner:
    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            raise GitCommandError(args, 128, "fatal: not a git repository\n")
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner


_FAKE_REPO = Path("/fake/repo")


@pytest.fixture
def sample_log_text() -> str:
    return (_FIXTURES_DIR / "git_log_sample.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit tests for private helpers
# ---------------------------------------------------------------------------


class TestSplitBodyAndNumstat:
    def test_body_and_numstat_separated_by_blank(self) -> None:
        rest = "Fix the bug.\nSee issue #7\n\n5\t3\tsrc/foo.py\n1\t0\ttests/test_foo.py"
        body, stats = _split_body_and_numstat(rest)
        assert body == ["Fix the bug.", "See issue #7", ""]
        assert stats == ["5\t3\tsrc/foo.py", "1\t0\ttests/test_foo.py"]

    def test_empty_body_only_numstat(self) -> None:
        rest = "10\t2\tsrc/bar.py"
        body, stats = _split_body_and_numstat(rest)
        assert body == []
        assert stats == ["10\t2\tsrc/bar.py"]

    def test_empty_rest_gives_empty_lists(self) -> None:
        body, stats = _split_body_and_numstat("")
        assert stats == []
        assert "\n".join(body).strip() == ""

    def test_binary_file_numstat_line(self) -> None:
        rest = "-\t-\tassets/logo.png"
        body, stats = _split_body_and_numstat(rest)
        assert body == []
        assert stats == ["-\t-\tassets/logo.png"]

    def test_body_with_no_numstat(self) -> None:
        rest = "Just a message.\nNo stats here."
        body, stats = _split_body_and_numstat(rest)
        assert stats == []
        assert body == ["Just a message.", "No stats here."]


class TestSumNumstat:
    def test_normal_lines(self) -> None:
        ins, dels, files = _sum_numstat(["15\t3\tsrc/auth.py", "8\t1\ttests/test_auth.py"])
        assert ins == 23
        assert dels == 4
        assert files == 2

    def test_binary_file(self) -> None:
        ins, dels, files = _sum_numstat(["-\t-\tassets/logo.png"])
        assert ins == 0
        assert dels == 0
        assert files == 1

    def test_empty(self) -> None:
        ins, dels, files = _sum_numstat([])
        assert ins == 0
        assert dels == 0
        assert files == 0

    def test_mixed_binary_and_text(self) -> None:
        ins, dels, files = _sum_numstat(["5\t2\tsrc/a.py", "-\t-\tassets/img.png"])
        assert ins == 5
        assert dels == 2
        assert files == 2


# ---------------------------------------------------------------------------
# collect_commits integration with fake runner
# ---------------------------------------------------------------------------


def _collect(runner: GitRunner, **kwargs: object) -> list[object]:
    defaults: dict[str, object] = {
        "since": "2026-06-26T00:00:00+00:00",
        "until": "2026-06-26T23:59:59+00:00",
        "author": None,
        "include_merges": True,
    }
    defaults.update(kwargs)

    from standup_generator.git.collector import collect_commits

    return collect_commits(  # type: ignore[return-value]
        _FAKE_REPO,
        since=defaults["since"],  # type: ignore[arg-type]
        until=defaults["until"],  # type: ignore[arg-type]
        author=defaults["author"],  # type: ignore[arg-type]
        include_merges=bool(defaults["include_merges"]),
        runner=runner,
    )


class TestCollectCommits:
    def test_parses_all_commits(self, sample_log_text: str) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(sample_log_text),
        )
        assert len(commits) == 4

    def test_first_commit_fields(self, sample_log_text: str) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(sample_log_text),
        )
        c = commits[0]
        assert c.sha == "aaaa0000000000000000000000000000000000aa"
        assert c.short_sha == "aaaa0000"
        assert c.repo == "repo"
        assert c.author_name == "Alice Developer"
        assert c.author_email == "alice@example.com"
        assert c.subject == "feat(auth): add refresh-token rotation"
        assert c.body == "Implements RFC-compliant token rotation.\nCloses #42"
        assert c.files_changed == 2
        assert c.insertions == 23  # 15 + 8
        assert c.deletions == 4  # 3 + 1

    def test_timestamp_is_tz_aware(self, sample_log_text: str) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(sample_log_text),
        )
        assert commits[0].timestamp.tzinfo is not None

    def test_binary_file_counts_as_one_file_zero_lines(self, sample_log_text: str) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(sample_log_text),
        )
        c = commits[1]
        assert c.sha == "bbbb0000000000000000000000000000000000bb"
        assert c.files_changed == 1
        assert c.insertions == 0
        assert c.deletions == 0
        assert c.body == ""

    def test_merge_commit_no_numstat(self, sample_log_text: str) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(sample_log_text),
        )
        c = commits[3]
        assert c.sha == "dddd0000000000000000000000000000000000dd"
        assert c.files_changed == 0
        assert c.insertions == 0
        assert c.deletions == 0

    def test_empty_output_returns_empty_list(self) -> None:
        commits = collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=_make_fake_runner(""),
        )
        assert commits == []

    def test_not_git_repo_raises(self) -> None:
        with pytest.raises(NotAGitRepositoryError) as exc_info:
            collect_commits(
                _FAKE_REPO,
                since="2026-06-26T00:00:00+00:00",
                until="2026-06-26T23:59:59+00:00",
                author=None,
                include_merges=True,
                runner=_make_failing_revparse_runner(),
            )
        assert str(_FAKE_REPO) in str(exc_info.value)

    def test_author_flag_passed_to_git(self, sample_log_text: str) -> None:
        captured: list[list[str]] = []

        def capturing_runner(args: list[str], cwd: Path) -> str:
            captured.append(list(args))
            if args[0] == "rev-parse":
                return "true\n"
            return sample_log_text

        collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author="alice@example.com",
            include_merges=True,
            runner=capturing_runner,
        )
        log_args = next(a for a in captured if a[0] == "log")
        assert "--author=alice@example.com" in log_args

    def test_no_author_flag_omitted(self, sample_log_text: str) -> None:
        captured: list[list[str]] = []

        def capturing_runner(args: list[str], cwd: Path) -> str:
            captured.append(list(args))
            if args[0] == "rev-parse":
                return "true\n"
            return sample_log_text

        collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=capturing_runner,
        )
        log_args = next(a for a in captured if a[0] == "log")
        assert not any(a.startswith("--author") for a in log_args)

    def test_no_merges_flag_when_include_merges_false(self, sample_log_text: str) -> None:
        captured: list[list[str]] = []

        def capturing_runner(args: list[str], cwd: Path) -> str:
            captured.append(list(args))
            if args[0] == "rev-parse":
                return "true\n"
            return sample_log_text

        collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=False,
            runner=capturing_runner,
        )
        log_args = next(a for a in captured if a[0] == "log")
        assert "--no-merges" in log_args

    def test_no_merges_flag_absent_when_include_merges_true(self, sample_log_text: str) -> None:
        captured: list[list[str]] = []

        def capturing_runner(args: list[str], cwd: Path) -> str:
            captured.append(list(args))
            if args[0] == "rev-parse":
                return "true\n"
            return sample_log_text

        collect_commits(
            _FAKE_REPO,
            since="2026-06-26T00:00:00+00:00",
            until="2026-06-26T23:59:59+00:00",
            author=None,
            include_merges=True,
            runner=capturing_runner,
        )
        log_args = next(a for a in captured if a[0] == "log")
        assert "--no-merges" not in log_args

    def test_since_until_datetime_serialised_to_iso(self, sample_log_text: str) -> None:

        captured: list[list[str]] = []

        def capturing_runner(args: list[str], cwd: Path) -> str:
            captured.append(list(args))
            if args[0] == "rev-parse":
                return "true\n"
            return sample_log_text

        from datetime import datetime

        since_dt = datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC)
        until_dt = datetime(2026, 6, 26, 23, 59, 59, tzinfo=UTC)

        collect_commits(
            _FAKE_REPO,
            since=since_dt,
            until=until_dt,
            author=None,
            include_merges=True,
            runner=capturing_runner,
        )
        log_args = next(a for a in captured if a[0] == "log")
        assert f"--since={since_dt.isoformat()}" in log_args
        assert f"--until={until_dt.isoformat()}" in log_args
