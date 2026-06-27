from __future__ import annotations

from standup_generator.models import StandupReport
from standup_generator.renderers._format import empty_line, fmt_date, fmt_datetime


class MarkdownRenderer:
    def render(self, report: StandupReport) -> str:
        if report.is_empty:
            return empty_line(report)

        lines: list[str] = []

        lines.append(f"# Standup — {fmt_date(report.since)}")
        lines.append("")

        # Dormant narrative branch — populated by the future AI milestone.
        if report.narrative:
            lines.append(f"> {report.narrative}")
            lines.append("")

        if report.author:
            lines.append(f"**Author:** {report.author}")
        lines.append(f"**Window:** {fmt_datetime(report.since)} → {fmt_datetime(report.until)}")
        n_repos = len(report.repos)
        commit_word = "commit" if report.total_commits == 1 else "commits"
        repo_word = "repo" if n_repos == 1 else "repos"
        lines.append(
            f"**Totals:** {report.total_commits} {commit_word} · "
            f"+{report.total_insertions} / -{report.total_deletions} · "
            f"{n_repos} {repo_word}"
        )

        for repo_summary in report.repos:
            lines.append("")
            commit_word_r = "commit" if repo_summary.commit_count == 1 else "commits"
            lines.append(
                f"## {repo_summary.repo} — "
                f"{repo_summary.commit_count} {commit_word_r} "
                f"(+{repo_summary.insertions} / -{repo_summary.deletions})"
            )
            for group in repo_summary.groups:
                lines.append("")
                lines.append(f"### {group.title}")
                for commit in group.commits:
                    lines.append(f"- `{commit.short_sha}` {commit.subject}")

        return "\n".join(lines)
