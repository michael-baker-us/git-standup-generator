"""Command-line entry point.

This is the ONLY module permitted to read the real clock, build the real
subprocess-backed git runner, and write to stdout.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from standup_generator import __version__
from standup_generator.config import Config, OutputFormat, load_config
from standup_generator.errors import StandupError
from standup_generator.git.collector import collect_commits
from standup_generator.git.runner import GitRunner, subprocess_runner
from standup_generator.logging_setup import configure_logging
from standup_generator.models import Commit
from standup_generator.renderers.base import Renderer
from standup_generator.renderers.markdown import MarkdownRenderer
from standup_generator.renderers.text import TextRenderer
from standup_generator.summarizers.template import TemplateSummarizer
from standup_generator.timerange import RangePreset, resolve_range

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="standup",
    help="Generate a standup summary from local git history.",
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def run(config: Config, *, now: datetime, runner: GitRunner) -> str:
    """Pure orchestration — testable with injected fakes."""
    # Resolve author via git config if not set and all_authors is False.
    author: str | None = config.author
    if not config.all_authors and author is None and config.repos:
        try:
            raw = runner(["config", "user.email"], config.repos[0])
            resolved = raw.strip()
            author = resolved if resolved else None
        except Exception:
            logger.warning("Could not resolve git config user.email; including all authors.")

    # Determine time window.
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
            # TODO(plan): approxidate strings cannot be parsed; best-effort use now
            since_dt = now
        until_dt = now
    else:
        since_dt, until_dt = resolve_range(config.range_preset, now)
        since_arg = since_dt
        until_arg = until_dt

    # Collect commits from all repos.
    all_commits: list[Commit] = []
    for repo in config.repos:
        repo_commits = collect_commits(
            repo,
            since=since_arg,
            until=until_arg,
            author=author,
            include_merges=config.include_merges,
            runner=runner,
        )
        all_commits.extend(repo_commits)

    report = TemplateSummarizer().summarize(
        all_commits,
        since=since_dt,
        until=until_dt,
        author=author,
    )

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
        typer.Option("--repo", "-r", help="Repo path (repeatable). Default: config or CWD."),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Explicit start (ISO or approxidate). Overrides --range."),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Explicit end. Default: now."),
    ] = None,
    range_preset: Annotated[
        RangePreset,
        typer.Option("--range", help="Preset time range."),
    ] = RangePreset.LAST_WORKING_DAY,
    author: Annotated[
        str | None,
        typer.Option("--author", "-a", help="Filter by author (name/email substring)."),
    ] = None,
    all_authors: Annotated[
        bool,
        typer.Option("--all-authors", help="Include all authors (overrides --author)."),
    ] = False,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.TEXT,
    include_merges: Annotated[
        bool,
        typer.Option("--include-merges", help="Include merge commits."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to a config file."),
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
    try:
        resolved_repos = tuple(repos) if repos else None
        config = load_config(
            repos=resolved_repos,
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
        result = run(config, now=now, runner=subprocess_runner)
        typer.echo(result)
    except StandupError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
