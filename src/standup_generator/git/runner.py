from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from standup_generator.errors import GitCommandError

GitRunner = Callable[[list[str], Path], str]
"""Run `git <args>` in `cwd`, return stdout. Raise GitCommandError on non-zero exit."""


def subprocess_runner(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitCommandError(args, result.returncode, result.stderr)
    return result.stdout
