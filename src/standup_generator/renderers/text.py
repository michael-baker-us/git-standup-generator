from __future__ import annotations

from standup_generator.models import StandupReport
from standup_generator.renderers._format import empty_line

# Left-justify subjects to this width so the short SHA aligns in a consistent column.
_SUBJECT_WIDTH = 46


class TextRenderer:
    def render(self, report: StandupReport) -> str:
        if report.is_empty:
            return empty_line(report)

        lines: list[str] = []

        # Dormant narrative branch — populated by the future AI milestone.
        if report.narrative:
            lines.append(f"Summary: {report.narrative}")
            lines.append("")

        # Header: Standup — Fri 2026-06-26 → Fri 2026-06-26  (author: email)
        since_str = report.since.strftime("%a %Y-%m-%d")
        until_str = report.until.strftime("%a %Y-%m-%d")
        header = f"Standup — {since_str} → {until_str}"
        if report.author:
            header += f"  (author: {report.author})"
        lines.append(header)

        # Totals: 3 commits · +412 / -88 across 2 repos
        n_repos = len(report.repos)
        commit_word = "commit" if report.total_commits == 1 else "commits"
        repo_word = "repo" if n_repos == 1 else "repos"
        lines.append(
            f"{report.total_commits} {commit_word} · "
            f"+{report.total_insertions} / -{report.total_deletions} "
            f"across {n_repos} {repo_word}"
        )

        lines.append("")

        for repo_summary in report.repos:
            commit_word_r = "commit" if repo_summary.commit_count == 1 else "commits"
            lines.append(
                f"{repo_summary.repo}  "
                f"({repo_summary.commit_count} {commit_word_r}, "
                f"+{repo_summary.insertions}/-{repo_summary.deletions})"
            )
            for group in repo_summary.groups:
                lines.append(f"  {group.title}")
                for commit in group.commits:
                    lines.append(f"    • {commit.subject:<{_SUBJECT_WIDTH}}{commit.short_sha}")

        return "\n".join(lines)
