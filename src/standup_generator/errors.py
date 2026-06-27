"""User-facing error hierarchy."""

from __future__ import annotations

from pathlib import Path


class StandupError(Exception):
    """Base class for all expected, user-facing errors."""


class NotAGitRepositoryError(StandupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Not a git repository: {path}")
        self.path = path


class GitCommandError(StandupError):
    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        super().__init__(f"git {' '.join(args)} failed ({returncode}): {stderr.strip()}")
        # TODO(plan): self.args conflicts with Exception.args under mypy strict
        self.cmd_args = args
        self.returncode = returncode
        self.stderr = stderr


class ConfigError(StandupError):
    """Malformed config file or invalid option combination."""
