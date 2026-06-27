# Git Standup Generator

Generate a standup summary from your local git history. Point it at one or more
repositories and it prints what you committed "since the last working day" as
plain text or markdown — ready to paste into Slack or your standup notes.

> **Status:** early development. The implementation is being built milestone by
> milestone per [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).
> Milestone **M0 (scaffolding)** is complete: the package installs and
> `standup --version` works. Collection, summarization, and rendering land in
> later milestones.

## Requirements

- Python 3.11+
- `git` available on your `PATH`

## Install (development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
standup --version
```

Full command surface (flags, config file, range semantics) is specified in the
implementation plan and will be documented here as it ships.

## Development

```bash
ruff check .          # lint
ruff format .         # format
mypy                  # type-check (strict)
pytest                # tests + coverage
```

## How it works

Commits are read from local git, grouped per repository and categorized by
[Conventional Commits](https://www.conventionalcommits.org/) prefix, then
rendered. Summarization sits behind a small `Summarizer` interface so an
AI-powered summary can be added later without touching collection or rendering —
see the "Future milestones" section of the implementation plan.

## License

MIT
