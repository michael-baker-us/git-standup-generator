# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-26

### Added
- `standup` CLI command (Typer) with `--repo`, `--since`, `--until`, `--range`, `--author`,
  `--all-authors`, `--format`, `--include-merges`, `--config`, `--verbose`, and `--version` flags.
- Deterministic template summarizer that groups commits by conventional-commit type
  (feat, fix, perf, refactor, docs, test, build/ci/chore, style, revert, other).
- Text and Markdown renderers; dormant `narrative` field for the future AI summarizer seam.
- Git commit collector with control-character delimiters, numstat parsing, and binary-file handling.
- Time-range presets: `last-working-day` (default), `yesterday`, `today`, `week`.
- Config file support (`.standup.toml` / XDG) with CLI flag override precedence.
- `StandupError` hierarchy for user-facing errors; exits with code 1 on expected failures.
- GitHub Actions CI workflow: matrix on Python 3.11/3.12; ruff, mypy, pytest with ≥ 90% coverage.
- Integration test suite using a real temporary git repository.

[0.1.0]: https://github.com/michaelbakerus/git-standup-generator/releases/tag/v0.1.0
