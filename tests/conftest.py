"""Shared pytest fixtures for standup-generator tests."""

from __future__ import annotations

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


def make_failing_revparse_runner() -> GitRunner:
    """Fake runner that raises GitCommandError on rev-parse (simulates non-repo path)."""

    def runner(args: list[str], cwd: Path) -> str:
        if args[0] == "rev-parse":
            raise GitCommandError(args, 128, "fatal: not a git repository\n")
        raise RuntimeError(f"Unexpected git call: git {' '.join(args)}")

    return runner
