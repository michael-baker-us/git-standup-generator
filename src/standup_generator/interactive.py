"""Interactive wizard — activated by --interactive / -i.

Prompts the user for source, date range, format, and output file using
arrow-key selection menus (questionary). All output goes to stderr so
stdout stays clean for the report itself.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from standup_generator.config import OutputFormat
from standup_generator.errors import StandupError
from standup_generator.timerange import RangePreset


@dataclass
class WizardResult:
    repos: tuple[Path, ...] | None
    scan_dirs: tuple[Path, ...] | None
    range_preset: RangePreset
    output_format: OutputFormat
    output_file: Path | None


def run_wizard() -> WizardResult:  # pragma: no cover
    """Run the interactive wizard and return resolved options."""
    if not sys.stdin.isatty():
        raise StandupError("--interactive requires an interactive terminal (TTY).")

    try:
        import questionary
    except ImportError as exc:
        raise StandupError("questionary is required for interactive mode") from exc

    # ── Source ────────────────────────────────────────────────────────────────
    source = cast(
        str,
        questionary.select(
            "Where should I look for commits?",
            choices=[
                questionary.Choice("Scan a directory for git repos", value="scan"),
                questionary.Choice("Use current directory", value="cwd"),
                questionary.Choice("Specify repo path(s)", value="repos"),
            ],
        ).ask(),
    )
    if source is None:
        raise typer_exit()

    repos: tuple[Path, ...] | None = None
    scan_dirs: tuple[Path, ...] | None = None

    if source == "scan":
        default_dir = str(Path.home() / "repos")
        raw_dir = cast(str, questionary.path("Directory to scan:", default=default_dir).ask())
        if raw_dir is None:
            raise typer_exit()
        scan_dirs = (Path(raw_dir).expanduser(),)

    elif source == "repos":
        raw_repos = cast(
            str,
            questionary.text(
                "Repo path(s) — comma-separated:",
                default=str(Path.cwd()),
            ).ask(),
        )
        if raw_repos is None:
            raise typer_exit()
        repos = tuple(Path(p.strip()).expanduser() for p in raw_repos.split(",") if p.strip())

    # ── Date range ────────────────────────────────────────────────────────────
    range_preset = cast(
        RangePreset,
        questionary.select(
            "Date range:",
            choices=[
                questionary.Choice("Last working day", value=RangePreset.LAST_WORKING_DAY),
                questionary.Choice("Yesterday", value=RangePreset.YESTERDAY),
                questionary.Choice("Today (so far)", value=RangePreset.TODAY),
                questionary.Choice("Past week   (7 days)", value=RangePreset.WEEK),
                questionary.Choice("Past month  (30 days)", value=RangePreset.MONTH),
                questionary.Choice("Past quarter (90 days)", value=RangePreset.QUARTER),
            ],
        ).ask(),
    )
    if range_preset is None:
        raise typer_exit()

    # ── Output format ─────────────────────────────────────────────────────────
    fmt = cast(
        OutputFormat,
        questionary.select(
            "Output format:",
            choices=[
                questionary.Choice("Text (plain)", value=OutputFormat.TEXT),
                questionary.Choice("Markdown", value=OutputFormat.MARKDOWN),
            ],
        ).ask(),
    )
    if fmt is None:
        raise typer_exit()

    # ── Output file ───────────────────────────────────────────────────────────
    raw_out = cast(
        str,
        questionary.text("Save report to file? (leave blank for stdout):", default="").ask(),
    )
    output_file = Path(raw_out.strip()).expanduser() if raw_out and raw_out.strip() else None

    return WizardResult(
        repos=repos,
        scan_dirs=scan_dirs,
        range_preset=range_preset,
        output_format=fmt,
        output_file=output_file,
    )


def typer_exit() -> SystemExit:
    """Return a SystemExit so the caller can raise it on wizard cancellation."""
    return SystemExit(0)
