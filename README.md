# Git Standup Generator

Generate a standup summary from your local git history. Point it at one or
more repositories and it prints what you committed since the last working day
as plain text or markdown — ready to paste into Slack or your standup notes.

## Requirements

- Python 3.11+
- `git` on your `PATH`

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

After install the `standup` command is on your PATH:

```bash
standup --version   # → 0.1.0
```

## Quick start

```bash
# Summarise everything you committed since the last working day (default).
standup

# Use the repository at a specific path instead of CWD.
standup --repo ~/code/api

# Two repos in one report.
standup --repo ~/code/api --repo ~/code/web

# Markdown output — pipe to a file or clipboard.
standup --format markdown > standup.md

# Show yesterday only.
standup --range yesterday

# Filter to your commits (useful in shared repos).
standup --author you@example.com
```

## All flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--repo PATH` | `-r` | CWD or config | Repo path. Repeatable for multiple repos. |
| `--since TEXT` | | — | Explicit start date (ISO 8601 or git approxidate). Overrides `--range`. |
| `--until TEXT` | | now | Explicit end date. |
| `--range PRESET` | | `last-working-day` | Time range preset. One of `last-working-day`, `yesterday`, `today`, `week`. |
| `--author TEXT` | `-a` | resolved from `git config user.email` | Filter commits by author name/email substring. |
| `--all-authors` | | off | Include all authors; overrides `--author`. |
| `--format FORMAT` | `-f` | `text` | Output format: `text` or `markdown`. |
| `--include-merges` | | off | Include merge commits (excluded by default). |
| `--config PATH` | `-c` | auto-discovered | Path to a TOML config file. |
| `--verbose` | `-v` | off | Log debug info to stderr (repo paths, git commands, commit counts). |
| `--version` | | | Print version and exit. |
| `--help` | `-h` | | Show help and exit. |

### Range presets

| Preset | Since |
|--------|-------|
| `last-working-day` | Start of the most recent prior weekday (see below). |
| `yesterday` | Start of yesterday. |
| `today` | Start of today (00:00 local time). |
| `week` | Start of the day 7 calendar days ago. |

`--since` and `--until` accept ISO 8601 dates (`2026-06-01`) or any string
git understands as an approxidate (`"2 days ago"`, `"last monday"`).

## Config file

`standup` looks for a config file in this order:

1. `--config <path>` (explicit flag)
2. `.standup.toml` in the current directory
3. `$XDG_CONFIG_HOME/standup/config.toml` (fallback: `~/.config/standup/config.toml`)

Example `.standup.toml`:

```toml
repos = ["~/code/api", "~/code/web"]
author = "you@example.com"
range = "last-working-day"
format = "markdown"
include_merges = false
```

Precedence: CLI flag > config file > built-in default.

All keys are optional. Unknown keys are rejected with a clear error.

## "Since last working day" semantics

The `last-working-day` preset is designed for the morning standup ritual: it
always covers the most recent workday, no matter what day of the week you run it.

| Day you run standup | `since` resolves to |
|---------------------|---------------------|
| Monday | Previous Friday (3 days back) |
| Saturday | Previous Friday (1 day back) |
| Sunday | Previous Friday (2 days back) |
| Tuesday – Friday | Previous calendar day |

`since` is the **start of that day** (00:00:00 local time); `until` is now.
On Monday morning this means the full Friday is included, which avoids losing
work done late on Friday.

## Output formats

### Text (default)

```
Standup — Thu 2026-06-25 → Fri 2026-06-26  (author: you@example.com)
3 commits · +412 / -88 across 2 repos

api  (2 commits, +300/-40)
  Features
    • feat(auth): add refresh-token rotation        a1b2c3d4
    • feat: paginate the /users endpoint            e5f6a7b8
web  (1 commit, +112/-48)
  Fixes
    • fix: guard against null session on logout      99ccaa11
```

### Markdown (`--format markdown`)

```markdown
# Standup — 2026-06-26

**Author:** you@example.com
**Window:** 2026-06-25 00:00 → 2026-06-26 09:15
**Totals:** 3 commits · +412 / -88 · 2 repos

## api — 2 commits (+300 / -40)

### Features
- `a1b2c3d4` feat(auth): add refresh-token rotation
- `e5f6a7b8` feat: paginate the /users endpoint

## web — 1 commit (+112 / -48)

### Fixes
- `99ccaa11` fix: guard against null session on logout
```

Commits are categorized by [Conventional Commits](https://www.conventionalcommits.org/)
prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, etc.).
Commits without a recognized prefix appear under **Other**.

## How summarization works / extending with AI

Commits are collected from `git log`, parsed into typed `Commit` objects, and
passed to a `Summarizer`. Today that is `TemplateSummarizer`: a pure, fully
deterministic function that groups commits by repo and category and aggregates
stats. No network, no LLM.

The `Summarizer` is a Protocol (structural interface):

```python
class Summarizer(Protocol):
    def summarize(
        self,
        commits: Sequence[Commit],
        *,
        since: datetime,
        until: datetime,
        author: str | None,
    ) -> StandupReport: ...
```

A future `ClaudeSummarizer` will implement this same interface, reuse
`TemplateSummarizer` for grouping/stats, and call the Claude API to fill
`StandupReport.narrative` with a prose paragraph. Both text and markdown
renderers already check for `narrative` and will display it when present —
**no renderer changes needed** when the AI summarizer lands.

To add your own summarizer: implement the `Summarizer` Protocol in
`src/standup_generator/summarizers/` and wire it up in `cli.py`.

## Development

```bash
ruff check .          # lint
ruff format .         # format
mypy                  # type-check (strict)
pytest                # unit tests + coverage
pytest -m integration # integration tests only (require real git)
pytest --cov-fail-under=90   # enforce coverage floor
```

### Project layout

```
src/standup_generator/
  cli.py              # Typer app — only place that reads the clock or calls subprocess
  config.py           # Config dataclass + TOML loading
  models.py           # Commit, RepoSummary, StandupReport (frozen dataclasses)
  timerange.py        # RangePreset + resolve_range()
  git/
    runner.py         # GitRunner type + real subprocess runner
    collector.py      # collect_commits() — git log → list[Commit]
  summarizers/
    base.py           # Summarizer Protocol
    template.py       # TemplateSummarizer (deterministic, no network)
  renderers/
    base.py           # Renderer Protocol
    text.py           # TextRenderer
    markdown.py       # MarkdownRenderer
```

The two injection seams — the clock (`datetime`) and the git runner
(`GitRunner`) — are passed in rather than called directly, making the whole
pipeline unit-testable without subprocess or frozen time.

## License

MIT
