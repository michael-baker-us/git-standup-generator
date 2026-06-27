"""AI-powered summarizer — fills StandupReport.narrative via the Claude API."""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from standup_generator.errors import StandupError
from standup_generator.models import Commit, StandupReport
from standup_generator.summarizers.template import TemplateSummarizer

if TYPE_CHECKING:
    import anthropic as _anthropic

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _build_prompt(report: StandupReport) -> str:
    since_str = report.since.strftime("%a %b %-d")
    until_str = report.until.strftime("%a %b %-d, %Y")
    days = max(1, (report.until - report.since).days)
    author_line = f"Author: {report.author}" if report.author else "Author: all contributors"

    lines: list[str] = [
        "You are summarizing a software engineer's git commits for their daily standup.",
        "",
        f"Time period: {since_str} → {until_str} ({days} days)",
        author_line,
        "",
        "Commits by repository:",
    ]

    for repo in report.repos:
        lines.append("")
        lines.append(
            f"## {repo.repo} — {repo.commit_count} commits "
            f"(+{repo.insertions} / -{repo.deletions} lines)"
        )
        for group in repo.groups:
            lines.append(f"\n{group.title}:")
            for commit in group.commits:
                subject = commit.subject
                body = commit.body.strip()
                entry = f"  - {subject}"
                if body:
                    entry += f" ({body[:120]})" if len(body) > 120 else f" ({body})"
                lines.append(entry)

    lines += [
        "",
        "---",
        "",
        "Write 2–4 sentences summarizing what was accomplished. Requirements:",
        "- Natural, first-person past tense (e.g. 'I added...', 'I fixed...')",
        "- Highlight the main themes and outcomes — do not list every commit",
        "- Suitable to read aloud at a standup meeting",
        "- No bullet points or markdown formatting in the response",
    ]

    return "\n".join(lines)


class ClaudeSummarizer:
    """Wraps TemplateSummarizer and enriches the report with a Claude-generated narrative."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        client: _anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        self._client = client
        self._template = TemplateSummarizer()

    def _get_client(self) -> _anthropic.Anthropic:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise StandupError(
                "AI summaries require the anthropic package.\n"
                "Install it with:  pip install 'git-standup-generator[ai]'"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise StandupError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Get your key at https://console.anthropic.com then:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )
        return anthropic.Anthropic(api_key=api_key)

    def summarize(
        self,
        commits: Sequence[Commit],
        *,
        since: datetime,
        until: datetime,
        author: str | None,
    ) -> StandupReport:
        report = self._template.summarize(commits, since=since, until=until, author=author)
        if report.is_empty:
            return report
        narrative = self._generate_narrative(report)
        return dataclasses.replace(report, narrative=narrative)

    def _generate_narrative(self, report: StandupReport) -> str:
        client = self._get_client()
        prompt = _build_prompt(report)
        message = client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        block = message.content[0]
        if block.type != "text":
            raise StandupError("Unexpected response type from Claude API")
        return block.text.strip()
