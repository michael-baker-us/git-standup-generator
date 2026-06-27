from __future__ import annotations

from pathlib import Path


def find_git_repos(scan_dir: Path) -> list[Path]:
    """Return immediate subdirectories of scan_dir that are git repos, sorted by name."""
    scan_dir = scan_dir.expanduser()
    if not scan_dir.is_dir():
        return []
    return sorted(
        child for child in scan_dir.iterdir() if child.is_dir() and (child / ".git").is_dir()
    )
