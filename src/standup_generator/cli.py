"""Command-line entry point.

This is the ONLY module permitted to read the real clock, build the real
subprocess-backed git runner, and write to stdout.

Default behaviour: when no source flag (--repo / --scan-dir / --since) is
supplied and stdout is a TTY, the full-screen TUI launches automatically.
Pass any source flag to run non-interactively (useful for scripting).
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from standup_generator import __version__
from standup_generator.config import Config, OutputFormat, load_config
from standup_generator.errors import StandupError
from standup_generator.git.collector import collect_commits
from standup_generator.git.discover import find_git_repos
from standup_generator.git.runner import GitRunner, subprocess_runner
from standup_generator.logging_setup import configure_logging
from standup_generator.models import Commit
from standup_generator.renderers.base import Renderer
from standup_generator.renderers.markdown import MarkdownRenderer
from standup_generator.renderers.text import TextRenderer
from standup_generator.summarizers.base import Summarizer
from standup_generator.summarizers.template import TemplateSummarizer
from standup_generator.timerange import RangePreset, resolve_range

logger = logging.getLogger(__name__)

_stderr = Console(stderr=True)

app = typer.Typer(
    name="standup",
    help=(
        "Generate a standup summary from local git history.\n\n"
        "Run with no arguments to open the interactive UI."
    ),
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def run(
    config: Config,
    *,
    now: datetime,
    runner: GitRunner,
    summarizer: Summarizer | None = None,
) -> str:
    """Pure orchestration — testable with injected fakes."""
    repos: list[Path] = []
    seen: set[Path] = set()
    for repo in config.repos:
        key = repo.resolve()
        if key not in seen:
            seen.add(key)
            repos.append(repo)
    for scan_dir in config.scan_dirs:
        for repo in find_git_repos(scan_dir):
            key = repo.resolve()
            if key not in seen:
                seen.add(key)
                repos.append(repo)

    author: str | None = config.author
    if not config.all_authors and author is None and repos:
        try:
            raw = runner(["config", "user.email"], repos[0])
            email = raw.strip()
            author = email if email else None
        except Exception:
            logger.warning("Could not resolve git config user.email; including all authors.")

    since_arg: datetime | str
    until_arg: datetime | str
    since_dt: datetime
    until_dt: datetime

    if config.since is not None:
        since_arg = config.since
        until_arg = config.until if config.until is not None else now.isoformat()
        try:
            since_dt = datetime.fromisoformat(config.since)
        except ValueError:
            since_dt = now
        until_dt = now
    else:
        since_dt, until_dt = resolve_range(config.range_preset, now)
        since_arg = since_dt
        until_arg = until_dt

    all_commits: list[Commit] = []
    for repo in repos:
        repo_commits = collect_commits(
            repo,
            since=since_arg,
            until=until_arg,
            author=author,
            include_merges=config.include_merges,
            runner=runner,
        )
        all_commits.extend(repo_commits)

    _summarizer: Summarizer = summarizer if summarizer is not None else TemplateSummarizer()
    report = _summarizer.summarize(all_commits, since=since_dt, until=until_dt, author=author)

    renderer: Renderer = (
        TextRenderer() if config.output_format is OutputFormat.TEXT else MarkdownRenderer()
    )
    return renderer.render(report)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    repos: Annotated[
        list[Path] | None,
        typer.Option("--repo", "-r", help="Repo path (repeatable). Bypasses the UI."),
    ] = None,
    scan_dirs: Annotated[
        list[Path] | None,
        typer.Option("--scan-dir", "-s", help="Directory to scan for git repos. Bypasses the UI."),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Explicit start date (ISO or approxidate). Bypasses the UI."),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Explicit end date. Default: now."),
    ] = None,
    range_preset: Annotated[
        RangePreset,
        typer.Option("--range", help="Preset time range."),
    ] = RangePreset.LAST_WORKING_DAY,
    author: Annotated[
        str | None,
        typer.Option("--author", "-a", help="Filter by author email/name substring."),
    ] = None,
    all_authors: Annotated[
        bool,
        typer.Option("--all-authors", help="Include all authors (overrides --author)."),
    ] = False,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.TEXT,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write report to file instead of stdout."),
    ] = None,
    ai: Annotated[
        bool,
        typer.Option("--ai", help="Use Claude to write a narrative summary."),
    ] = False,
    model: Annotated[
        str,
        typer.Option("--model", help="Claude model for --ai.", show_default=True),
    ] = "claude-haiku-4-5-20251001",
    include_merges: Annotated[
        bool,
        typer.Option("--include-merges", help="Include merge commits."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to a TOML config file."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Log debug info to stderr."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Generate a standup summary from local git history."""
    configure_logging(verbose)

    # ── Default: launch the full-screen TUI ───────────────────────────────────
    # Any source flag (--repo, --scan-dir, --since) signals scripting intent and
    # bypasses the TUI so the tool stays pipeable.
    no_source = repos is None and scan_dirs is None and since is None
    if no_source and sys.stdout.isatty():  # pragma: no cover
        from standup_generator.tui import launch

        launch()
        return

    # ── Non-interactive (scripting / CI) path ─────────────────────────────────
    try:
        config = load_config(
            repos=tuple(repos) if repos else None,
            scan_dirs=tuple(scan_dirs) if scan_dirs else None,
            author=author,
            all_authors=all_authors,
            range_preset=range_preset,
            since=since,
            until=until,
            output_format=fmt,
            include_merges=include_merges,
            verbose=verbose,
            config_path=config_path,
        )
        now = datetime.now(UTC).astimezone()

        chosen_summarizer: Summarizer
        if ai:
            from standup_generator.summarizers.claude import ClaudeSummarizer

            chosen_summarizer = ClaudeSummarizer(model=model)
            spinner_msg = "[dim]Collecting commits and generating AI summary…[/dim]"
        else:
            chosen_summarizer = TemplateSummarizer()
            spinner_msg = "[dim]Collecting commits…[/dim]"

        with _stderr.status(spinner_msg, spinner="dots"):
            result = run(config, now=now, runner=subprocess_runner, summarizer=chosen_summarizer)

        if output is not None:
            output.write_text(result, encoding="utf-8")
            _stderr.print(f"[green]✓[/green] Report saved to [bold]{output}[/bold]")
        else:
            typer.echo(result)

    except StandupError as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
