from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Sequence

from standup_generator.models import CategoryGroup, Commit, RepoSummary, StandupReport

_TYPE_TO_TITLE: dict[str, str] = {
    "feat": "Features",
    "fix": "Fixes",
    "perf": "Performance",
    "refactor": "Refactors",
    "docs": "Docs",
    "test": "Tests",
    "build": "Chores",
    "ci": "Chores",
    "chore": "Chores",
    "style": "Style",
    "revert": "Reverts",
}

_TITLE_ORDER: list[str] = [
    "Features",
    "Fixes",
    "Performance",
    "Refactors",
    "Docs",
    "Tests",
    "Chores",
    "Style",
    "Reverts",
    "Other",
]

_CC_RE = re.compile(r"^(\w+)(\(.+\))?(!)?:")


def categorize(subject: str) -> str:
    """Return the category title for a commit subject line."""
    m = _CC_RE.match(subject)
    if m:
        return _TYPE_TO_TITLE.get(m.group(1), "Other")
    return "Other"


class TemplateSummarizer:
    def summarize(
        self,
        commits: Sequence[Commit],
        *,
        since: datetime,
        until: datetime,
        author: str | None,
    ) -> StandupReport:
        # Group commits by repo, preserving first-seen order.
        repo_commits: dict[str, list[Commit]] = {}
        for commit in commits:
            if commit.repo not in repo_commits:
                repo_commits[commit.repo] = []
            repo_commits[commit.repo].append(commit)

        repo_summaries: list[RepoSummary] = []
        total_commits = 0
        total_insertions = 0
        total_deletions = 0

        for repo_name, repo_commit_list in repo_commits.items():
            by_title: dict[str, list[Commit]] = defaultdict(list)
            for commit in repo_commit_list:
                by_title[categorize(commit.subject)].append(commit)

            groups: list[CategoryGroup] = [
                CategoryGroup(title=title, commits=tuple(by_title[title]))
                for title in _TITLE_ORDER
                if title in by_title
            ]

            ins = sum(c.insertions for c in repo_commit_list)
            dels = sum(c.deletions for c in repo_commit_list)
            files = sum(c.files_changed for c in repo_commit_list)
            count = len(repo_commit_list)

            repo_summaries.append(
                RepoSummary(
                    repo=repo_name,
                    groups=tuple(groups),
                    commit_count=count,
                    insertions=ins,
                    deletions=dels,
                    files_changed=files,
                )
            )
            total_commits += count
            total_insertions += ins
            total_deletions += dels

        return StandupReport(
            since=since,
            until=until,
            author=author,
            repos=tuple(repo_summaries),
            total_commits=total_commits,
            total_insertions=total_insertions,
            total_deletions=total_deletions,
            narrative=None,
        )
