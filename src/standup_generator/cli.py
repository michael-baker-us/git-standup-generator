"""Command-line entry point.

This is the ONLY module permitted to read the real clock, build the real
subprocess-backed git runner, and write to stdout. Later milestones add the
orchestration; for now M0 only wires up `--version` so the package installs and
runs cleanly.
"""

from __future__ import annotations

import typer

from standup_generator import __version__

app = typer.Typer(
    name="standup",
    help="Generate a standup summary from local git history.",
    add_completion=False,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Generate a standup summary from local git history."""
    # Orchestration is implemented in milestone M5. For now this is a no-op shell
    # so `standup --version` works and the command exits cleanly.


if __name__ == "__main__":
    app()
