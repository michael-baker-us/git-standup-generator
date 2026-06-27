from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from standup_generator.models import CategoryGroup, Commit, RepoSummary, StandupReport
from standup_generator.renderers.markdown import MarkdownRenderer
from standup_generator.renderers.text import TextRenderer

_TZ = UTC
_SINCE = datetime(2026, 6, 26, 0, 0, 0, tzinfo=_TZ)
_UNTIL = datetime(2026, 6, 26, 9, 15, 0, tzinfo=_TZ)


def _commit(sha_prefix: str, subject: str, repo: str, ins: int, dels: int) -> Commit:
    return Commit(
        repo=repo,
        sha=sha_prefix + "0" * (40 - len(sha_prefix)),
        author_name="Test User",
        author_email="test@example.com",
        timestamp=_SINCE,
        subject=subject,
        body="",
        files_changed=1,
        insertions=ins,
        deletions=dels,
    )


@pytest.fixture
def sample_report() -> StandupReport:
    c1 = _commit("a1b2c3d4", "feat(auth): add refresh-token rotation", "api", 200, 20)
    c2 = _commit("e5f6a7b8", "feat: paginate the /users endpoint", "api", 100, 20)
    c3 = _commit("99ccaa11", "fix: guard against null session on logout", "web", 112, 48)
    api_summary = RepoSummary(
        repo="api",
        groups=(CategoryGroup(title="Features", commits=(c1, c2)),),
        commit_count=2,
        insertions=300,
        deletions=40,
        files_changed=2,
    )
    web_summary = RepoSummary(
        repo="web",
        groups=(CategoryGroup(title="Fixes", commits=(c3,)),),
        commit_count=1,
        insertions=112,
        deletions=48,
        files_changed=1,
    )
    return StandupReport(
        since=_SINCE,
        until=_UNTIL,
        author="michaelbakerus@gmail.com",
        repos=(api_summary, web_summary),
        total_commits=3,
        total_insertions=412,
        total_deletions=88,
    )


@pytest.fixture
def empty_with_author() -> StandupReport:
    return StandupReport(
        since=_SINCE,
        until=_UNTIL,
        author="michaelbakerus@gmail.com",
        repos=(),
        total_commits=0,
        total_insertions=0,
        total_deletions=0,
    )


@pytest.fixture
def empty_no_author() -> StandupReport:
    return StandupReport(
        since=_SINCE,
        until=_UNTIL,
        author=None,
        repos=(),
        total_commits=0,
        total_insertions=0,
        total_deletions=0,
    )


class TestTextRenderer:
    def test_header_contains_dates_and_author(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        assert "Standup — Fri 2026-06-26 → Fri 2026-06-26" in output
        assert "(author: michaelbakerus@gmail.com)" in output

    def test_totals_line(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        assert "3 commits · +412 / -88 across 2 repos" in output

    def test_repo_headers(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        assert "api  (2 commits, +300 / -40)" in output
        assert "web  (1 commit, +112 / -48)" in output

    def test_category_headings(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        assert "  Features" in output
        assert "  Fixes" in output

    def test_commit_lines_have_bullet_subject_sha(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        lines_by_subject = {ln: ln for ln in output.split("\n") if "feat(auth)" in ln}
        assert len(lines_by_subject) == 1
        commit_line = next(iter(lines_by_subject))
        assert commit_line.startswith("    •")
        assert "feat(auth): add refresh-token rotation" in commit_line
        assert "a1b2c3d4" in commit_line

    def test_fix_commit_line(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        fix_lines = [ln for ln in output.split("\n") if "null session on logout" in ln]
        assert len(fix_lines) == 1
        assert "99ccaa11" in fix_lines[0]

    def test_repo_order_preserved(self, sample_report: StandupReport) -> None:
        output = TextRenderer().render(sample_report)
        assert output.index("api") < output.index("web")

    def test_empty_with_author(self, empty_with_author: StandupReport) -> None:
        output = TextRenderer().render(empty_with_author)
        assert output == (
            "No commits found for michaelbakerus@gmail.com "
            "between 2026-06-26 00:00 and 2026-06-26 09:15."
        )

    def test_empty_no_author(self, empty_no_author: StandupReport) -> None:
        output = TextRenderer().render(empty_no_author)
        assert output == "No commits found between 2026-06-26 00:00 and 2026-06-26 09:15."

    def test_no_author_omits_author_clause(self, sample_report: StandupReport) -> None:
        report = dataclasses.replace(sample_report, author=None)
        output = TextRenderer().render(report)
        assert "(author:" not in output

    def test_narrative_prepended_before_header(self, sample_report: StandupReport) -> None:
        report = dataclasses.replace(sample_report, narrative="Worked on auth and session fixes.")
        output = TextRenderer().render(report)
        assert "Summary: Worked on auth and session fixes." in output
        assert output.index("Summary:") < output.index("Standup")

    def test_singular_commit_and_repo(self) -> None:
        c = _commit("aabbccdd", "fix: a small fix", "solo", 5, 2)
        summary = RepoSummary(
            repo="solo",
            groups=(CategoryGroup(title="Fixes", commits=(c,)),),
            commit_count=1,
            insertions=5,
            deletions=2,
            files_changed=1,
        )
        report = StandupReport(
            since=_SINCE,
            until=_UNTIL,
            author=None,
            repos=(summary,),
            total_commits=1,
            total_insertions=5,
            total_deletions=2,
        )
        output = TextRenderer().render(report)
        assert "1 commit ·" in output
        assert "across 1 repo" in output
        assert "solo  (1 commit," in output


class TestMarkdownRenderer:
    def test_title(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "# Standup — 2026-06-26" in output

    def test_author_line(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "**Author:** michaelbakerus@gmail.com" in output

    def test_window_line(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "**Window:** 2026-06-26 00:00 → 2026-06-26 09:15" in output

    def test_totals_line(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "**Totals:** 3 commits · +412 / -88 · 2 repos" in output

    def test_repo_headings(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "## api — 2 commits (+300 / -40)" in output
        assert "## web — 1 commit (+112 / -48)" in output

    def test_category_headings(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "### Features" in output
        assert "### Fixes" in output

    def test_commit_lines(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert "- `a1b2c3d4` feat(auth): add refresh-token rotation" in output
        assert "- `e5f6a7b8` feat: paginate the /users endpoint" in output
        assert "- `99ccaa11` fix: guard against null session on logout" in output

    def test_repo_order_preserved(self, sample_report: StandupReport) -> None:
        output = MarkdownRenderer().render(sample_report)
        assert output.index("## api") < output.index("## web")

    def test_empty_with_author(self, empty_with_author: StandupReport) -> None:
        output = MarkdownRenderer().render(empty_with_author)
        assert output == (
            "No commits found for michaelbakerus@gmail.com "
            "between 2026-06-26 00:00 and 2026-06-26 09:15."
        )

    def test_empty_no_author(self, empty_no_author: StandupReport) -> None:
        output = MarkdownRenderer().render(empty_no_author)
        assert output == "No commits found between 2026-06-26 00:00 and 2026-06-26 09:15."

    def test_no_author_omits_author_line(self, sample_report: StandupReport) -> None:
        report = dataclasses.replace(sample_report, author=None)
        output = MarkdownRenderer().render(report)
        assert "**Author:**" not in output

    def test_narrative_blockquote_after_title_before_metadata(
        self, sample_report: StandupReport
    ) -> None:
        report = dataclasses.replace(sample_report, narrative="Summary of auth work.")
        output = MarkdownRenderer().render(report)
        assert "> Summary of auth work." in output
        assert output.index("> Summary") > output.index("# Standup")
        assert output.index("> Summary") < output.index("**Author:**")

    def test_singular_commit_and_repo(self) -> None:
        c = _commit("aabbccdd", "fix: a small fix", "solo", 5, 2)
        summary = RepoSummary(
            repo="solo",
            groups=(CategoryGroup(title="Fixes", commits=(c,)),),
            commit_count=1,
            insertions=5,
            deletions=2,
            files_changed=1,
        )
        report = StandupReport(
            since=_SINCE,
            until=_UNTIL,
            author=None,
            repos=(summary,),
            total_commits=1,
            total_insertions=5,
            total_deletions=2,
        )
        output = MarkdownRenderer().render(report)
        assert "**Totals:** 1 commit ·" in output
        assert "· 1 repo" in output
        assert "## solo — 1 commit " in output
