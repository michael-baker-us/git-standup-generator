# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`git-standup-generator` is a CLI (`standup`) that reads local git history across one or
more repos and prints what you committed in a time window as text or markdown. Pure stdlib +
Typer; no network, no LLM (yet — see "Summarizer seam" below).

## Commands

```bash
pip install -e ".[dev]"        # install with dev deps; puts `standup` on PATH

ruff check .                   # lint
ruff format .                  # format (CI enforces `ruff format --check .`)
mypy                           # type-check (strict; files = src + tests)
pytest                         # all tests + coverage (term-missing report is default)
pytest -m integration          # only the real-git end-to-end tests
pytest -m "not integration"    # skip integration tests
pytest --cov-fail-under=90     # coverage floor enforced in CI
pytest tests/test_config.py::test_name   # single test
```

CI (`.github/workflows/ci.yml`) runs ruff check, ruff format --check, mypy, and pytest
with `--cov-fail-under=90` on Python 3.11 and 3.12. Match all four locally before pushing.

## Architecture

The pipeline is a one-way data flow, each stage a pure function operating on frozen
dataclasses (`models.py`): `git log` → `collect_commits` → `list[Commit]` →
`Summarizer.summarize` → `StandupReport` → `Renderer.render` → string.

`cli.py` is deliberately the **only** module allowed to touch the outside world: it reads
the real clock (`datetime.now`), builds the real `subprocess_runner`, and writes stdout.
Everything else is pure. The two injection seams are:

- **The clock** — `now: datetime` is threaded explicitly into `run()` and `resolve_range()`.
- **The git runner** — `GitRunner = Callable[[list[str], Path], str]` (`git/runner.py`).
  Tests pass a fake runner that returns canned `git log` output; no subprocess, no frozen time.

`cli.run(config, *, now, runner)` is the pure orchestrator — test it directly with fakes
rather than going through Typer.

### Config precedence

`load_config` (`config.py`) merges three sources, **CLI flag > TOML file > built-in default**,
key by key. The file is auto-discovered: `--config` flag, then `./.standup.toml`, then
`$XDG_CONFIG_HOME/standup/config.toml` (fallback `~/.config/standup/config.toml`). Unknown
TOML keys are rejected (`_ALLOWED_TOML_KEYS`). When adding a config option you must touch all
three: the `Config` dataclass field, the `load_config` merge block, and the `_ALLOWED_TOML_KEYS`
set — plus the Typer option in `cli.py`.

### Commit collection parsing

`collect_commits` (`git/collector.py`) is the trickiest code. It runs `git log --numstat`
with a `%x1f`-delimited pretty format and uses `%x1e` as a **leading** per-commit separator
(not trailing) — because `--numstat` output is appended *after* the pretty body, a trailing
separator would split records incorrectly. Each record is then split into header fields + body,
and `_split_body_and_numstat` peels the maximal trailing run of numstat lines off the body.
Binary files show `-` in numstat and count as 0 insertions/deletions. See the in-code
`TODO(plan)` comment before changing the log format.

### Summarizer seam (the AI extension point)

`Summarizer` and `Renderer` are `Protocol`s (`summarizers/base.py`, `renderers/base.py`).
Today the only summarizer is `TemplateSummarizer` — deterministic grouping of commits by repo
and Conventional-Commits category, with stat aggregation, no network. `StandupReport.narrative`
is reserved (`None`) for a future `ClaudeSummarizer` that implements the same Protocol, reuses
`TemplateSummarizer` for grouping/stats, and fills `narrative` via the Claude API. Both
renderers already render `narrative` when present, so adding the AI summarizer needs **no
renderer changes** — implement the Protocol and wire it into `cli.run`.

### Errors

All user-facing errors subclass `StandupError` (`errors.py`). `cli.main` catches `StandupError`,
prints `Error: ...` to stderr, and exits 1. Raise these (not bare exceptions) for anything the
user should see as a clean message.
