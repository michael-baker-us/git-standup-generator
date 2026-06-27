"""Tests for cli.py — run() pure function and Typer CLI surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from standup_generator import __version__
from standup_generator.cli import app, run
from standup_generator.config import Config, OutputFormat
from standup_generator.errors import GitCommandError, NotAGitRepositoryError
from standup_generator.git.runner import GitRunner
from standup_generator.timerange import RangePreset

_FIXED_NOW = datetime(2026, 6, 26, 9, 0, 0, tzinfo=UTC)

_SAMPLE_LOG = (
    "\x1eabc1234567890abcdef1234567890abcdef12345678"
    "\x1fAlice\x1falice@example.com\x1f2026-06-25T22:00:00+00:00"
    "\x1ffeat: add login page\x1f\n"
    "10\t2\tsrc/login.py\n"
)


def _make_runner(log_output: str, email: str = "alice@example.com") -> GitRunner:
    """Fake runner supporting rev-parse, log, and git config user.email."""

    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            return "true\n"
        if args[0] == "log":
            return log_output
        if args[:2] == ["config", "user.email"]:
            return f"{email}\n"
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner


def _make_config(
    repo: Path,
    *,
    author: str | None = None,
    all_authors: bool = False,
    output_format: OutputFormat = OutputFormat.TEXT,
    range_preset: RangePreset = RangePreset.YESTERDAY,
    since: str | None = None,
    until: str | None = None,
    include_merges: bool = False,
    verbose: bool = False,
    scan_dirs: tuple[Path, ...] = (),
) -> Config:
    return Config(
        repos=(repo,),
        scan_dirs=scan_dirs,
        author=author,
        all_authors=all_authors,
        range_preset=range_preset,
        since=since,
        until=until,
        output_format=output_format,
        include_merges=include_merges,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# run() direct tests
# ---------------------------------------------------------------------------


def test_run_text_format(tmp_path: Path) -> None:
    config = _make_config(tmp_path, author="alice@example.com", output_format=OutputFormat.TEXT)
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    assert "Standup" in result
    assert "feat: add login page" in result


def test_run_markdown_format(tmp_path: Path) -> None:
    config = _make_config(tmp_path, author="alice@example.com", output_format=OutputFormat.MARKDOWN)
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    assert result.startswith("# Standup")
    assert "feat: add login page" in result
    assert "abc12345" in result


def test_run_empty_no_commits(tmp_path: Path) -> None:
    config = _make_config(tmp_path, author="alice@example.com")
    result = run(config, now=_FIXED_NOW, runner=_make_runner(""))
    assert "No commits found" in result


def test_run_author_resolved_from_git_config(tmp_path: Path) -> None:
    """When config.author is None and all_authors is False, author comes from git config."""
    config = _make_config(tmp_path, author=None, all_authors=False)
    fake = _make_runner(_SAMPLE_LOG, email="alice@example.com")
    result = run(config, now=_FIXED_NOW, runner=fake)
    # Report header should show the resolved author.
    assert "alice@example.com" in result


def test_run_all_authors_skips_resolution(tmp_path: Path) -> None:
    """When all_authors=True, no git config call is made; report has no author."""
    calls: list[list[str]] = []

    def tracking_runner(args: list[str], cwd: Path) -> str:
        calls.append(args)
        if args[0] == "rev-parse":
            return "true\n"
        if args[0] == "log":
            return _SAMPLE_LOG
        raise RuntimeError(f"Unexpected: git {' '.join(args)}")

    config = _make_config(tmp_path, all_authors=True)
    run(config, now=_FIXED_NOW, runner=tracking_runner)
    config_calls = [a for a in calls if a[:1] == ["config"]]
    assert config_calls == [], "Should not call git config when all_authors=True"


def test_run_author_resolution_failure_falls_back(tmp_path: Path) -> None:
    """If git config user.email fails, author is None (all authors included)."""

    def failing_runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            return "true\n"
        if args[0] == "log":
            return ""
        if args[:2] == ["config", "user.email"]:
            raise GitCommandError(args, 1, "error\n")
        raise RuntimeError(f"Unexpected: git {' '.join(args)}")

    config = _make_config(tmp_path, author=None, all_authors=False)
    result = run(config, now=_FIXED_NOW, runner=failing_runner)
    assert "No commits found" in result  # empty output, no crash


def test_run_not_a_git_repo_raises(tmp_path: Path) -> None:
    from standup_generator.errors import NotAGitRepositoryError

    def bad_runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            raise GitCommandError(args, 128, "fatal: not a git repository\n")
        if args[:2] == ["config", "user.email"]:
            return "alice@example.com\n"
        raise RuntimeError(f"Unexpected: git {' '.join(args)}")

    config = _make_config(tmp_path, author="alice@example.com")
    with pytest.raises(NotAGitRepositoryError):
        run(config, now=_FIXED_NOW, runner=bad_runner)


def test_run_explicit_since_used(tmp_path: Path) -> None:
    config = _make_config(
        tmp_path,
        author="alice@example.com",
        since="2026-06-01",
        until="2026-06-26",
    )
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    assert "feat: add login page" in result


def test_run_multi_repo(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    config = Config(
        repos=(repo_a, repo_b),
        scan_dirs=(),
        author="alice@example.com",
        all_authors=False,
        range_preset=RangePreset.YESTERDAY,
        since=None,
        until=None,
        output_format=OutputFormat.TEXT,
        include_merges=False,
        verbose=False,
    )
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    # Commits from both repos appear; repo names are directory basenames.
    assert result.count("feat: add login page") == 2


# ---------------------------------------------------------------------------
# Typer CLI surface tests (via CliRunner)
# ---------------------------------------------------------------------------

_CLI_RUNNER = CliRunner()


def test_cli_version() -> None:
    result = _CLI_RUNNER.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_cli_standup_error_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """StandupError from run() → exit code 1 with 'Error:' on stderr."""

    def bad_runner(args: list[str], cwd: Path) -> str:
        if args[:2] == ["config", "user.email"]:
            return "alice@example.com\n"
        raise NotAGitRepositoryError(cwd)

    monkeypatch.chdir(tmp_path)
    import standup_generator.cli as cli_mod

    monkeypatch.setattr(cli_mod, "subprocess_runner", bad_runner)

    result = _CLI_RUNNER.invoke(app, [])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_cli_default_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full CLI run with monkeypatched runner produces text output."""
    monkeypatch.chdir(tmp_path)
    import standup_generator.cli as cli_mod

    monkeypatch.setattr(cli_mod, "subprocess_runner", _make_runner(_SAMPLE_LOG))

    result = _CLI_RUNNER.invoke(app, [])
    assert result.exit_code == 0
    assert "feat: add login page" in result.output


def test_run_scan_dir_discovers_repos(tmp_path: Path) -> None:
    """Repos found via scan_dirs are included in the report."""
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    config = Config(
        repos=(),
        scan_dirs=(tmp_path,),
        author="alice@example.com",
        all_authors=False,
        range_preset=RangePreset.YESTERDAY,
        since=None,
        until=None,
        output_format=OutputFormat.TEXT,
        include_merges=False,
        verbose=False,
    )
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    assert "feat: add login page" in result


def test_run_scan_dir_deduplicates(tmp_path: Path) -> None:
    """A repo present in both repos and scan_dirs is collected only once."""
    repo_dir = tmp_path / "myrepo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    config = Config(
        repos=(repo_dir,),
        scan_dirs=(tmp_path,),
        author="alice@example.com",
        all_authors=False,
        range_preset=RangePreset.YESTERDAY,
        since=None,
        until=None,
        output_format=OutputFormat.TEXT,
        include_merges=False,
        verbose=False,
    )
    result = run(config, now=_FIXED_NOW, runner=_make_runner(_SAMPLE_LOG))
    assert result.count("feat: add login page") == 1


def test_cli_format_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--format markdown produces markdown output."""
    monkeypatch.chdir(tmp_path)
    import standup_generator.cli as cli_mod

    monkeypatch.setattr(cli_mod, "subprocess_runner", _make_runner(_SAMPLE_LOG))

    result = _CLI_RUNNER.invoke(app, ["--format", "markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("# Standup")
