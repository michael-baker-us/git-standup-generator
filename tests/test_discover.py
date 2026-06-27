"""Tests for git/discover.py — find_git_repos."""

from __future__ import annotations

from pathlib import Path

import pytest

from standup_generator.git.discover import find_git_repos


def _make_git_dir(parent: Path, name: str) -> Path:
    """Create a directory that looks like a git repo (has a .git subdir)."""
    d = parent / name
    d.mkdir()
    (d / ".git").mkdir()
    return d


def test_finds_git_repos(tmp_path: Path) -> None:
    git_a = _make_git_dir(tmp_path, "alpha")
    _plain = tmp_path / "beta"
    _plain.mkdir()
    git_b = _make_git_dir(tmp_path, "gamma")

    result = find_git_repos(tmp_path)
    assert result == [git_a, git_b]


def test_sorted_by_name(tmp_path: Path) -> None:
    _make_git_dir(tmp_path, "zebra")
    _make_git_dir(tmp_path, "ant")
    _make_git_dir(tmp_path, "mango")

    result = find_git_repos(tmp_path)
    assert [r.name for r in result] == ["ant", "mango", "zebra"]


def test_empty_directory(tmp_path: Path) -> None:
    assert find_git_repos(tmp_path) == []


def test_no_git_subdirs(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    (tmp_path / "also-plain").mkdir()
    assert find_git_repos(tmp_path) == []


def test_nonexistent_directory(tmp_path: Path) -> None:
    assert find_git_repos(tmp_path / "does-not-exist") == []


def test_tilde_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _make_git_dir(tmp_path, "myrepo")
    result = find_git_repos(Path("~"))
    assert len(result) == 1
    assert result[0].name == "myrepo"


def test_ignores_git_files_not_dirs(tmp_path: Path) -> None:
    """A .git file (worktree) should not count — only .git directories."""
    d = tmp_path / "worktree-repo"
    d.mkdir()
    (d / ".git").write_text("gitdir: /some/other/path\n")
    assert find_git_repos(tmp_path) == []
