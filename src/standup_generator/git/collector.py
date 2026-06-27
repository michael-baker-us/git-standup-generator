from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from standup_generator.errors import GitCommandError, NotAGitRepositoryError
from standup_generator.git.runner import GitRunner
from standup_generator.models import Commit

logger = logging.getLogger(__name__)

_NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t.+$")


def _split_body_and_numstat(rest: str) -> tuple[list[str], list[str]]:
    """Split the trailing numstat lines from the body text.

    Returns (body_lines, stat_lines). Numstat block is the maximal trailing
    run of lines matching the numstat regex; everything before it is the body.
    """
    lines = rest.split("\n")
    split_idx = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if _NUMSTAT_RE.match(lines[i]):
            split_idx = i
        else:
            break
    return lines[:split_idx], lines[split_idx:]


def _sum_numstat(stat_lines: list[str]) -> tuple[int, int, int]:
    """Return (insertions, deletions, files_changed). Binary files show '-', treated as 0."""
    insertions = deletions = files = 0
    for line in stat_lines:
        parts = line.split("\t", 2)
        insertions += 0 if parts[0] == "-" else int(parts[0])
        deletions += 0 if parts[1] == "-" else int(parts[1])
        files += 1
    return insertions, deletions, files


def collect_commits(
    repo: Path,
    *,
    since: datetime | str,
    until: datetime | str,
    author: str | None,
    include_merges: bool,
    runner: GitRunner,
) -> list[Commit]:
    """Collect commits from `repo` in the given time window via the provided runner."""
    try:
        runner(["rev-parse", "--is-inside-work-tree"], repo)
    except GitCommandError as exc:
        raise NotAGitRepositoryError(repo) from exc

    repo_name = repo.resolve().name
    since_str = since.isoformat() if isinstance(since, datetime) else since
    until_str = until.isoformat() if isinstance(until, datetime) else until

    # TODO(plan): spec says --pretty=format:%H%x1f...%b%x1e (with %x1e trailing the body),
    # but real git places numstat AFTER the pretty output, so %x1e ends up BEFORE numstat.
    # Splitting on \x1e then gives records that each contain numstat from the PREVIOUS commit
    # mixed with the current commit's header — the parse algorithm breaks. Using %x1e as a
    # leading per-commit separator instead, which produces self-contained, parseable records.
    args: list[str] = [
        "log",
        f"--since={since_str}",
        f"--until={until_str}",
        "--numstat",
        "--date=iso-strict",
        "--pretty=format:%x1e%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%b",
    ]
    if author is not None:
        args.append(f"--author={author}")
    if not include_merges:
        args.append("--no-merges")

    logger.debug("Running: git %s in %s", " ".join(args), repo)
    output = runner(args, repo)

    records = [r for r in output.split("\x1e") if r.strip()]
    commits: list[Commit] = []

    for record in records:
        parts = record.lstrip("\n").split("\x1f")
        if len(parts) < 6:
            continue
        sha, an, ae, aI, subject = parts[0], parts[1], parts[2], parts[3], parts[4]
        rest = parts[5].strip()

        body_lines, stat_lines = _split_body_and_numstat(rest)
        insertions, deletions, files_changed = _sum_numstat(stat_lines)

        commits.append(
            Commit(
                repo=repo_name,
                sha=sha,
                author_name=an,
                author_email=ae,
                timestamp=datetime.fromisoformat(aI),
                subject=subject,
                body="\n".join(body_lines).strip(),
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )
        )

    logger.debug("Collected %d commits from %s", len(commits), repo_name)
    return commits
