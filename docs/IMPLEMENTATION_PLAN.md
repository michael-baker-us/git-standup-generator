# Git Standup Generator — Implementation Plan

> **Audience:** an implementing AI (e.g. Claude Sonnet) building this from an empty repo.
> **Rule of thumb:** Build in the milestone order below. Do **not** start a milestone until the
> previous milestone's *Acceptance gate* passes. Each milestone is self-contained and verifiable.
> When something is ambiguous, prefer the simplest option that satisfies the stated contract and
> leave a `# TODO(milestone-N):` note rather than inventing scope.

---

## 1. What we are building

A command-line tool that reads commits from one or more **local** git repositories for a time
window (default: "since the last working day") and prints a **standup summary** to stdout in
**text** or **markdown**.

The summary is produced by a **deterministic template summarizer** in the MVP. The code is
structured around a `Summarizer` interface so a Claude-powered summarizer can be added later
**without touching the collector, models, renderers, or CLI**.

### Locked product decisions
| Decision | Choice |
|---|---|
| Language / runtime | **Python 3.11+** (uses stdlib `tomllib`) |
| Summary engine | **Deterministic template now**, AI later via the `Summarizer` seam |
| Data source | **Local git only** (no network, no GitHub API in MVP) |
| Output | **stdout**, `--format text` (default) or `--format markdown` |
| CLI framework | **Typer** |
| Test framework | **pytest** |
| Lint / format | **ruff** |
| Types | full type hints; checked with **mypy** |

### Explicit non-goals for the MVP
- No network calls of any kind (no GitHub, no LLM).
- No writing to files or clipboard (stdout only; users pipe/redirect themselves).
- No interactive prompts. The tool is non-interactive and pipe-friendly.

---

## 2. Architecture

Layered, with **dependency injection** at the two boundaries that touch the outside world
(the system clock and the `git` subprocess). This is what makes the whole thing unit-testable
without shelling out or freezing time.

```
CLI (Typer)                         cli.py
  └─ orchestrates:
       config         ───────────►  config.py        (load TOML + merge CLI flags)
       time range     ───────────►  timerange.py      (compute since/until from a clock)
       collection     ───────────►  git/collector.py  (run git, parse → list[Commit])
       summarization  ───────────►  summarizers/      (Commit[] → StandupReport)
       rendering      ───────────►  renderers/        (StandupReport → str)
  └─ prints rendered string to stdout; logs to stderr
```

**Data flows one direction.** Lower layers never import the CLI. Models have no behavior beyond
trivial derived properties.

### Injection seams (critical — implement exactly)
- **Clock:** functions that need "now" accept `now: datetime` (tz-aware) as a parameter. The CLI
  passes `datetime.now(timezone.utc).astimezone()`. Tests pass a fixed datetime. **Never call
  `datetime.now()` outside `cli.py`.**
- **Git runner:** `collector` accepts a `runner: GitRunner` callable
  (`Callable[[list[str], Path], str]`) that takes git args + cwd and returns stdout. The CLI passes
  the real subprocess runner. Unit tests pass a stub returning canned git output. **Never call
  `subprocess` outside `git/runner.py`.**

---

## 3. Project layout

```
git-standup-generator/
├─ pyproject.toml
├─ README.md
├─ .gitignore
├─ .ruff.toml                     # or [tool.ruff] in pyproject
├─ docs/
│  └─ IMPLEMENTATION_PLAN.md      # this file
├─ src/
│  └─ standup_generator/
│     ├─ __init__.py              # __version__ = "0.1.0"
│     ├─ __main__.py              # enables `python -m standup_generator`
│     ├─ cli.py                   # Typer app, orchestration, the ONLY place with now()/print
│     ├─ config.py                # Config dataclass + load/merge
│     ├─ models.py                # Commit, RepoSummary, StandupReport, etc. (frozen dataclasses)
│     ├─ timerange.py             # RangePreset, resolve_range(...)
│     ├─ errors.py                # StandupError hierarchy
│     ├─ logging_setup.py         # configure_logging(verbose: bool)
│     ├─ git/
│     │  ├─ __init__.py
│     │  ├─ runner.py             # real subprocess GitRunner + GitRunner type alias
│     │  └─ collector.py          # collect_commits(...) -> list[Commit]
│     ├─ summarizers/
│     │  ├─ __init__.py
│     │  ├─ base.py               # Summarizer Protocol
│     │  └─ template.py           # TemplateSummarizer
│     └─ renderers/
│        ├─ __init__.py
│        ├─ base.py               # Renderer Protocol
│        ├─ text.py               # TextRenderer
│        └─ markdown.py           # MarkdownRenderer
└─ tests/
   ├─ conftest.py                 # shared fixtures (sample commits, fake runner)
   ├─ fixtures/
   │  └─ git_log_sample.txt       # canned git output for parser tests
   ├─ test_timerange.py
   ├─ test_collector.py
   ├─ test_template_summarizer.py
   ├─ test_renderers.py
   ├─ test_config.py
   ├─ test_cli.py
   └─ test_integration_git.py     # creates a real temp repo, end-to-end
```

Use the **src layout** (package under `src/`). It prevents accidental imports of the local
working tree and forces an installed-package test setup.

---

## 4. Dependencies

`pyproject.toml` (PEP 621, hatchling backend):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "git-standup-generator"
version = "0.1.0"
description = "Generate a standup summary from local git history."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",   # CLI; pulls in click + rich
]

[project.scripts]
standup = "standup_generator.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.5",
    "mypy>=1.10",
]

[tool.hatch.build.targets.wheel]
packages = ["src/standup_generator"]

[tool.pytest.ini_options]
addopts = "-ra --cov=standup_generator --cov-report=term-missing"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src", "tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

> No third-party TOML, datetime, or git libraries. `tomllib` (read-only TOML) is stdlib in 3.11.
> Keep the dependency surface tiny — it makes the build reproducible and the tool easy to install.

---

## 5. Data models (`models.py`)

All frozen dataclasses. `from __future__ import annotations` at the top of every module.

```python
@dataclass(frozen=True, slots=True)
class Commit:
    repo: str               # display name of the repo (its directory basename)
    sha: str                # full 40-char hash
    author_name: str
    author_email: str
    timestamp: datetime     # tz-aware, authored date (%aI)
    subject: str            # first line of message
    body: str               # remaining message lines (may be "")
    files_changed: int      # 0 if not computable (e.g. merge/empty)
    insertions: int
    deletions: int

    @property
    def short_sha(self) -> str:
        return self.sha[:8]

@dataclass(frozen=True, slots=True)
class CategoryGroup:
    title: str                       # e.g. "Features", "Fixes", "Other"
    commits: tuple[Commit, ...]

@dataclass(frozen=True, slots=True)
class RepoSummary:
    repo: str
    groups: tuple[CategoryGroup, ...]
    commit_count: int
    insertions: int
    deletions: int
    files_changed: int

@dataclass(frozen=True, slots=True)
class StandupReport:
    since: datetime
    until: datetime
    author: str | None               # the filter that was applied, or None for all authors
    repos: tuple[RepoSummary, ...]
    total_commits: int
    total_insertions: int
    total_deletions: int
    # Reserved for the AI milestone; always None in the template summarizer.
    narrative: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.total_commits == 0
```

> **Why `narrative` lives here now:** the future `ClaudeSummarizer` will build the same
> `StandupReport` and fill `narrative` with prose. Renderers can show it when present and ignore it
> when `None`, so **no renderer change is needed** when AI lands.

---

## 6. Errors (`errors.py`)

```python
class StandupError(Exception):
    """Base class for all expected, user-facing errors."""

class NotAGitRepositoryError(StandupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Not a git repository: {path}")
        self.path = path

class GitCommandError(StandupError):
    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        super().__init__(f"git {' '.join(args)} failed ({returncode}): {stderr.strip()}")
        self.args = args
        self.returncode = returncode
        self.stderr = stderr

class ConfigError(StandupError):
    """Malformed config file or invalid option combination."""
```

The CLI catches `StandupError`, prints `Error: <message>` to **stderr**, and exits with code `1`.
Any other exception propagates (it's a bug, and we want the traceback in dev).

---

## 7. Time ranges (`timerange.py`)

```python
class RangePreset(str, Enum):
    LAST_WORKING_DAY = "last-working-day"   # default
    YESTERDAY = "yesterday"
    TODAY = "today"
    WEEK = "week"                            # last 7 calendar days

def resolve_range(preset: RangePreset, now: datetime) -> tuple[datetime, datetime]:
    """Return (since, until) as tz-aware datetimes, using `now` as the clock.
    `until` is always `now`. `since` is the start-of-day boundary per preset.
    """
```

**Semantics (implement exactly; these are the test cases):**
- `start_of_day(d)` = that date at `00:00:00` in `now`'s tzinfo.
- `TODAY`: since = start_of_day(now).
- `YESTERDAY`: since = start_of_day(now - 1 day).
- `WEEK`: since = start_of_day(now - 7 days).
- `LAST_WORKING_DAY`: since = start_of_day of the most recent **prior** weekday.
  - If `now` is Mon (weekday 0) → since = previous **Friday** (now - 3 days).
  - If `now` is Sun (6) → previous **Friday** (now - 2 days).
  - If `now` is Sat (5) → previous **Friday** (now - 1 day).
  - Otherwise (Tue–Fri) → previous calendar day (now - 1 day).
- Explicit `--since` / `--until` CLI flags (ISO date or git approxidate string) **bypass** presets
  and are passed to git verbatim; see §9.

`until` is always `now`.

---

## 8. Git collection

### 8.1 `git/runner.py`
```python
GitRunner = Callable[[list[str], Path], str]
"""Run `git <args>` in `cwd`, return stdout (text). Raise GitCommandError on non-zero exit."""

def subprocess_runner(args: list[str], cwd: Path) -> str:
    # subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    # On returncode != 0: raise GitCommandError(args, returncode, stderr)
    # Use encoding="utf-8", errors="replace".
```

### 8.2 `git/collector.py`
```python
def collect_commits(
    repo: Path,
    *,
    since: datetime | str,
    until: datetime | str,
    author: str | None,
    include_merges: bool,
    runner: GitRunner,
) -> list[Commit]:
    ...
```

Steps:
1. **Validate repo.** Run `["rev-parse", "--is-inside-work-tree"]`; if the runner raises
   `GitCommandError`, raise `NotAGitRepositoryError(repo)`.
2. **Resolve repo display name** = `repo.resolve().name`.
3. **Build the git log command** (see exact format below).
4. Run it via `runner`, parse stdout into `Commit` objects, return in the order git emits them
   (newest first).

### 8.3 Exact `git log` command
Use control characters as delimiters so commit messages can contain anything:
- Field separator: `\x1f` (Unit Separator) → write as `%x1f` in the pretty format.
- Record separator: `\x1e` (Record Separator) → `%x1e`.

```
git log
  --since=<since>
  --until=<until>
  [--author=<author>]        # omit if author is None
  [--no-merges]              # include when include_merges is False
  --numstat
  --date=iso-strict
  --pretty=format:%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1f%b%x1e
```

- For `since`/`until`: if a `datetime`, pass ISO 8601 (`.isoformat()`); if a `str`, pass as-is.
- `%b` (body) may contain newlines; that's fine because records are split on `\x1e`, not `\n`.

### 8.4 Exact parse algorithm
git emits, per commit: the `--pretty` line, then a blank line, then zero or more `--numstat` lines
(`<added>\t<deleted>\t<path>`), terminated by the record separator `\x1e` before the next commit.

```
text = runner_output
records = [r for r in text.split("\x1e") if r.strip()]
for record in records:
    # record looks like:  "<H>\x1f<an>\x1f<ae>\x1f<aI>\x1f<subject>\x1f<body>\n<numstat lines...>"
    header, _, numstat_blob = record.partition("\x1f<after the 6 header fields>")
    # Simpler: split the record into the 6 header fields + trailing numstat block.
    parts = record.lstrip("\n").split("\x1f")
    sha, an, ae, aI = parts[0], parts[1], parts[2], parts[3]
    subject = parts[4]
    # parts[5] = body + "\n" + numstat lines. Split body from numstat:
    rest = parts[5]
    # numstat lines match: ^\d+\t\d+\t.*  OR  ^-\t-\t.*  (binary files show "-")
    # Walk rest line by line from the END collecting numstat lines; everything before is body.
    body_lines, stat_lines = split_body_and_numstat(rest)
    insertions, deletions, files = sum_numstat(stat_lines)  # treat "-" as 0
    timestamp = datetime.fromisoformat(aI)
    append Commit(repo=name, sha=sha, ... timestamp=timestamp, subject=subject,
                  body="\n".join(body_lines).strip(), files_changed=files,
                  insertions=insertions, deletions=deletions)
```

`split_body_and_numstat(rest)`: a numstat line matches regex `^(\d+|-)\t(\d+|-)\t.+$`. Iterate lines;
the numstat block is the maximal trailing run of lines matching that regex. Everything before it is
the body. (Bodies don't end with tab-separated `int int path` triples, so the trailing-run heuristic
is safe; still, guard with the regex.)

`sum_numstat`: for each stat line, `added` and `deleted` are ints, or `0` when the field is `-`
(binary). `files = len(stat_lines)`.

> Edge cases to handle and test: empty output (no commits) → `[]`; a commit with an empty body;
> a commit touching a binary file (`-\t-\tlogo.png`); a merge commit when `include_merges=True`
> (numstat may be empty → counts are 0).

---

## 9. Configuration (`config.py`)

Precedence (highest wins): **CLI flag > env var (if any) > config file > built-in default.**

```python
@dataclass(frozen=True, slots=True)
class Config:
    repos: tuple[Path, ...]          # default: (Path.cwd(),)
    author: str | None               # default: resolved from `git config user.email` of first repo
    all_authors: bool                # default: False
    range_preset: RangePreset        # default: LAST_WORKING_DAY
    since: str | None                # explicit override (ISO or approxidate); default None
    until: str | None                # default None
    output_format: OutputFormat      # default: TEXT
    include_merges: bool             # default: False
    verbose: bool                    # default: False
```

`OutputFormat(str, Enum)`: `TEXT = "text"`, `MARKDOWN = "markdown"`.

**Config file discovery** (first that exists): `--config <path>` → `./.standup.toml` →
`$XDG_CONFIG_HOME/standup/config.toml` (fallback `~/.config/standup/config.toml`). Parse with
`tomllib`. Unknown keys → `ConfigError`. Example file documented in README:

```toml
# .standup.toml
repos = ["~/code/api", "~/code/web"]   # ~ is expanded
author = "michaelbakerus@gmail.com"
range = "last-working-day"
format = "markdown"
include_merges = false
```

**Author defaulting:** if `all_authors` is False and no `author` is set anywhere, resolve it by
running `git config user.email` in the first repo (via the runner). If that fails, fall back to
`None` and log a warning (effectively "all authors").

---

## 10. Summarizer seam

### 10.1 `summarizers/base.py`
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

### 10.2 `summarizers/template.py` — `TemplateSummarizer`
Pure function-style class, fully deterministic.

1. **Group commits by repo** (preserve first-seen repo order).
2. Within each repo, **categorize** each commit by the prefix of its subject using conventional
   commit types. Parse `^(\w+)(\(.+\))?(!)?:` from the subject; map the type to a title:
   | type | title |
   |---|---|
   | feat | Features |
   | fix | Fixes |
   | perf | Performance |
   | refactor | Refactors |
   | docs | Docs |
   | test | Tests |
   | build, ci, chore | Chores |
   | style | Style |
   | revert | Reverts |
   | (no/unknown prefix) | Other |

   Group order = the fixed order of the table above, then `Other` last. Drop empty groups.
3. **Aggregate stats per repo** (sum insertions/deletions/files; `commit_count = len`).
4. **Aggregate totals** across repos.
5. Return `StandupReport(narrative=None, ...)`. Repos with zero commits are omitted entirely.

> Keep categorization in a small pure helper `categorize(subject) -> str` so it's unit-tested in
> isolation.

---

## 11. Renderers

### 11.1 `renderers/base.py`
```python
class Renderer(Protocol):
    def render(self, report: StandupReport) -> str: ...
```

Renderers return a **string** (they do not print). The CLI prints. This keeps them trivially
snapshot-testable.

### 11.2 Empty report
Both renderers, when `report.is_empty`, return a single friendly line, e.g.
`No commits found for <author> between <since:%Y-%m-%d %H:%M> and <until:%Y-%m-%d %H:%M>.`
(omit "for <author>" when author is None).

### 11.3 `TextRenderer` (default) — example output
```
Standup — Fri 2026-06-26 → Fri 2026-06-26  (author: michaelbakerus@gmail.com)
3 commits · +412 / -88 across 2 repos

api  (2 commits, +300/-40)
  Features
    • feat(auth): add refresh-token rotation        a1b2c3d4
    • feat: paginate the /users endpoint            e5f6a7b8
web  (1 commit, +112/-48)
  Fixes
    • fix: guard against null session on logout      99ccaa11
```

### 11.4 `MarkdownRenderer` — example output
```markdown
# Standup — 2026-06-26

**Author:** michaelbakerus@gmail.com
**Window:** 2026-06-26 00:00 → 2026-06-26 09:15
**Totals:** 3 commits · +412 / −88 · 2 repos

## api — 2 commits (+300 / −40)

### Features
- `a1b2c3d4` feat(auth): add refresh-token rotation
- `e5f6a7b8` feat: paginate the /users endpoint

## web — 1 commit (+112 / −48)

### Fixes
- `99ccaa11` fix: guard against null session on logout
```

> If `report.narrative` is set (future AI), each renderer prepends/inserts it (text: a `Summary:`
> paragraph at top; markdown: a `> ` blockquote under the title). Implement this conditional now so
> the AI milestone needs zero renderer changes — just leave it dormant since `narrative` is `None`.

Date formatting helper lives in one place (`renderers/_format.py` or a shared function). Use
`%Y-%m-%d` and `%H:%M`. The `−` in totals can be a plain ASCII `-` to keep tests simple; pick one
and be consistent.

---

## 12. CLI (`cli.py`)

Typer app. This is the **only** module that: reads the real clock, constructs the real
`subprocess_runner`, and prints to stdout. It catches `StandupError`.

```
standup [OPTIONS]

Options:
  -r, --repo PATH               Repo path (repeatable). Default: config or CWD.
      --since TEXT              Explicit start (ISO date or git approxidate). Overrides --range.
      --until TEXT              Explicit end. Default: now.
      --range [last-working-day|yesterday|today|week]   Default: last-working-day.
  -a, --author TEXT             Filter by author (name/email substring).
      --all-authors             Include all authors (overrides --author).
  -f, --format [text|markdown]  Default: text.
      --include-merges          Include merge commits. Default: off.
  -c, --config PATH             Path to a config file.
  -v, --verbose                 Log debug info to stderr.
      --version                 Print version and exit.
  -h, --help
```

**Orchestration sequence:**
1. `configure_logging(verbose)`.
2. Load `Config` (file + CLI merge per §9).
3. `now = datetime.now(timezone.utc).astimezone()`.
4. Determine window: if `config.since` set → use raw strings (`since`, `until or now-iso`);
   else `since, until = resolve_range(config.range_preset, now)`.
5. For each repo: `collect_commits(...)` with `subprocess_runner`. Concatenate all commits.
   (Repo display names disambiguate them.) A `NotAGitRepositoryError` on one repo is fatal with a
   clear message — do not silently skip, since that hides mistakes.
6. `report = TemplateSummarizer().summarize(commits, since=..., until=..., author=...)`.
   - Note: when `--since` strings are used, also compute concrete datetimes for the report header.
     Simplest correct approach: keep `since`/`until` as the datetimes you pass to the summarizer.
     For raw approxidate strings where you can't easily get a datetime, parse with
     `datetime.fromisoformat` when possible; otherwise pass `now` for `until` and the parsed date
     for `since`, and document that the header reflects best-effort. (Test only the preset path
     for exact datetimes.)
7. `renderer = TextRenderer() if format is TEXT else MarkdownRenderer()`.
8. `typer.echo(renderer.render(report))`.
9. Exit 0. (Empty report still exits 0 — "no commits" is not an error.)

Wrap steps 2–8 so any `StandupError` → `typer.echo(f"Error: {e}", err=True); raise typer.Exit(1)`.

---

## 13. Logging (`logging_setup.py`)

```python
def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, stream=sys.stderr,
                        format="%(levelname)s %(name)s: %(message)s")
```

- All logs go to **stderr**; the report goes to **stdout**. This keeps `standup -f markdown > out.md`
  clean.
- Modules use `logger = logging.getLogger(__name__)`. Log the git command at DEBUG, commit counts at
  DEBUG, the author-resolution fallback at WARNING.

---

## 14. Testing strategy

Aim for **>90% line coverage**. The injection seams make this achievable without flakiness.

| Test file | What it asserts |
|---|---|
| `test_timerange.py` | Every preset for each weekday using fixed `now` values. Monday→Friday case explicitly. |
| `test_collector.py` | Parse `fixtures/git_log_sample.txt` via a **fake runner**: correct count, fields, body/numstat split, binary `-` handling, empty output → `[]`. `NotAGitRepositoryError` when rev-parse runner raises. |
| `test_template_summarizer.py` | `categorize()` table; grouping order; per-repo and total aggregation; multi-repo ordering; empty input. |
| `test_renderers.py` | Snapshot-style assertions on text + markdown for a known `StandupReport`; the empty-report line; (dormant) narrative branch when `narrative` is set. |
| `test_config.py` | Precedence merge; TOML parsing; `~` expansion; unknown key → `ConfigError`. |
| `test_cli.py` | `typer.testing.CliRunner`: `--version`; default run with a fake runner injected; `--format markdown`; a `StandupError` path exits 1 with `Error:` on stderr. |
| `test_integration_git.py` | Create a **real temp repo** (`tmp_path`), set user.name/email, make 3 commits across categories, run the real collector+summarizer+renderer end to end, assert commits appear. Mark `@pytest.mark.integration`. |

`conftest.py` provides: `sample_commits` fixture, a `fake_runner` factory (maps arg patterns →
canned stdout), and a `make_git_repo` helper for the integration test.

> For CLI tests to inject a fake runner, give `cli.py`'s core a thin indirection: a `_build_runner()`
> function (returns `subprocess_runner`) that tests can monkeypatch, **or** factor the orchestration
> into `run(config, *, now, runner) -> str` that `cli.py`'s Typer callback calls with real
> dependencies and tests call with fakes. **Prefer the latter** — a pure `run()` function is the
> cleanest test surface and keeps the Typer callback a thin shell.

---

## 15. Milestones & acceptance gates

Implement strictly in order. Each gate must pass before moving on.

### M0 — Scaffolding
- Create layout (§3), `pyproject.toml` (§4), `.gitignore` (Python), empty `README.md`, `__init__.py`
  with `__version__`.
- **Gate:** `pip install -e ".[dev]"` succeeds; `standup --version` prints `0.1.0`; `ruff check .`
  and `mypy` pass on the stub.

### M1 — Models, errors, time ranges (pure, no git)
- Implement `models.py`, `errors.py`, `timerange.py`. Write `test_timerange.py`.
- **Gate:** `pytest tests/test_timerange.py` green; mypy strict passes.

### M2 — Git collection
- Implement `git/runner.py`, `git/collector.py`. Add `fixtures/git_log_sample.txt` and
  `test_collector.py` (fake runner).
- **Gate:** collector tests green, including binary/empty/merge edge cases.

### M3 — Template summarizer
- Implement `summarizers/base.py`, `summarizers/template.py`, `test_template_summarizer.py`.
- **Gate:** summarizer tests green; grouping/order/aggregation correct.

### M4 — Renderers
- Implement `renderers/*`, `test_renderers.py` for text + markdown + empty + dormant narrative.
- **Gate:** renderer tests green; sample outputs match §11.

### M5 — Config + CLI wiring
- Implement `config.py`, `logging_setup.py`, the pure `run(...)` function, and `cli.py` Typer shell.
  Add `test_config.py`, `test_cli.py`.
- **Gate:** all unit tests green; `standup -f markdown` against this very repo prints a sensible
  summary; `ruff` + `mypy` clean.

### M6 — Integration + docs polish
- `test_integration_git.py` (real temp repo). Flesh out `README.md`: install, usage, all flags,
  config example, the "since last working day" semantics, and a "How summarization works /
  extending with AI" section pointing at the `Summarizer` seam.
- **Gate:** full `pytest` green incl. integration; coverage ≥ 90%; README complete.

### M7 — CI/CD & release hygiene (from the cross-project standards)
- `.github/workflows/ci.yml`: matrix Python 3.11/3.12; steps = install, `ruff check`,
  `ruff format --check`, `mypy`, `pytest --cov` with a coverage floor.
- Add `CHANGELOG.md` (Keep a Changelog) and tag `v0.1.0`.
- **Gate:** CI green on a PR.

---

## 16. Future milestones (designed-for, not built now)

These are the seams already in place so they slot in cleanly:

- **AI summarizer** — add `summarizers/claude.py` implementing `Summarizer`. It builds the same
  `StandupReport` (reuse `TemplateSummarizer` for grouping/stats) then calls the Claude API to fill
  `narrative`. Select it with `--summarizer template|claude` (or auto when `ANTHROPIC_API_KEY` is
  set). Renderers already handle `narrative`. Add network-error handling that **degrades to the
  template** so the tool never hard-fails offline. Use the latest model id (e.g. `claude-sonnet-4-6`
  or `claude-haiku-4-5-*`) — confirm current ids against the Claude API reference at build time.
- **GitHub source** — add a `sources/` package paralleling `git/`; merge PRs/issues into the same
  `Commit`-like stream or a new `Activity` model. Requires auth + rate-limit handling.
- **Output targets** — add `--output FILE` and `--copy` (clipboard) without touching renderers.

---

## 17. Conventions for the implementer
- `from __future__ import annotations` in every module.
- Type-hint everything; pass `mypy --strict`.
- No `datetime.now()` or `subprocess` outside their designated modules (§2 seams).
- Frozen dataclasses; no hidden mutable state; no module-level singletons.
- Renderers/summarizers are pure (input → string/report); side effects live only in `cli.py`.
- Commit per milestone with a conventional-commit message (`feat:`, `test:`, `docs:`, `ci:`).
- If a spec detail is genuinely missing, pick the simplest behavior consistent with the contracts
  above and mark it `# TODO(plan):` rather than expanding scope.
```

