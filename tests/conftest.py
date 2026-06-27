"""Shared pytest fixtures for standup-generator tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from standup_generator.errors import GitCommandError
from standup_generator.git.runner import GitRunner

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_log_text() -> str:
    return (_FIXTURES_DIR / "git_log_sample.txt").read_text(encoding="utf-8")


@pytest.fixture
def fake_runner_factory() -> object:
    """Return the make_fake_runner helper so tests can build custom fake runners."""
    return make_fake_runner


def make_fake_runner(log_output: str) -> GitRunner:
    """Fake runner: returns true for rev-parse, log_output for log commands."""

    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            return "true\n"
        if args[0] == "log":
            return log_output
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner


def make_git_repo(path: Path, commits: list[tuple[str, str]]) -> Path:
    """Create a real git repo in *path* with the given (filename, message) commits.

    Sets local user.name and user.email so the test is hermetic — no global config required.
    """

    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)

    _git("init")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test User")
    for filename, message in commits:
        (path / filename).write_text(f"# {filename}\n")
        _git("add", filename)
        _git("commit", "-m", message)
    return path


def make_failing_revparse_runner() -> GitRunner:
    """Fake runner that raises GitCommandError on rev-parse (simulates non-repo path)."""

    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            raise GitCommandError(args, 128, "fatal: not a git repository\n")
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner
