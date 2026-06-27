from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from standup_generator.errors import ConfigError
from standup_generator.timerange import RangePreset

logger = logging.getLogger(__name__)


class OutputFormat(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"


_ALLOWED_TOML_KEYS = frozenset(
    {"repos", "scan_dirs", "author", "all_authors", "range", "format", "include_merges", "verbose"}
)


@dataclass(frozen=True, slots=True)
class Config:
    repos: tuple[Path, ...]
    scan_dirs: tuple[Path, ...]
    author: str | None
    all_authors: bool
    range_preset: RangePreset
    since: str | None
    until: str | None
    output_format: OutputFormat
    include_merges: bool
    verbose: bool


def _find_config_file(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    local = Path.cwd() / ".standup.toml"
    if local.exists():
        return local
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        xdg_path = Path(xdg) / "standup" / "config.toml"
    else:
        xdg_path = Path.home() / ".config" / "standup" / "config.toml"
    if xdg_path.exists():
        return xdg_path
    return None


def _load_toml(path: Path) -> dict[str, object]:
    try:
        with open(path, "rb") as f:
            data: dict[str, object] = tomllib.load(f)
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Malformed config file {path}: {exc}") from exc
    unknown = set(data) - _ALLOWED_TOML_KEYS
    if unknown:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    return data


def load_config(
    *,
    repos: tuple[Path, ...] | None = None,
    scan_dirs: tuple[Path, ...] | None = None,
    author: str | None = None,
    all_authors: bool = False,
    range_preset: RangePreset | None = None,
    since: str | None = None,
    until: str | None = None,
    output_format: OutputFormat | None = None,
    include_merges: bool = False,
    verbose: bool = False,
    config_path: Path | None = None,
) -> Config:
    """Merge config file + CLI flags. CLI flags win; file wins over defaults."""
    file_data: dict[str, object] = {}
    found = _find_config_file(config_path)
    if found is not None:
        file_data = _load_toml(found)

    # scan_dirs: CLI > file > empty tuple
    resolved_scan_dirs: tuple[Path, ...]
    if scan_dirs is not None:
        resolved_scan_dirs = scan_dirs
    elif "scan_dirs" in file_data:
        raw_sd = file_data["scan_dirs"]
        if not isinstance(raw_sd, list):
            raise ConfigError("'scan_dirs' must be a list of strings")
        resolved_scan_dirs = tuple(Path(str(r)).expanduser() for r in raw_sd)
    else:
        resolved_scan_dirs = ()

    # repos: CLI > file > default (CWD, only when no scan_dirs are set)
    resolved_repos: tuple[Path, ...]
    if repos is not None:
        resolved_repos = repos
    elif "repos" in file_data:
        raw = file_data["repos"]
        if not isinstance(raw, list):
            raise ConfigError("'repos' must be a list of strings")
        resolved_repos = tuple(Path(str(r)).expanduser() for r in raw)
    elif not resolved_scan_dirs:
        resolved_repos = (Path.cwd(),)
    else:
        resolved_repos = ()

    # author: CLI > file > (resolved at runtime in run())
    resolved_author: str | None = author
    if resolved_author is None and "author" in file_data:
        resolved_author = str(file_data["author"])

    # all_authors: CLI > file > False
    resolved_all_authors: bool = all_authors
    if not resolved_all_authors and "all_authors" in file_data:
        raw_aa = file_data["all_authors"]
        if not isinstance(raw_aa, bool):
            raise ConfigError("'all_authors' must be a boolean")
        resolved_all_authors = raw_aa

    # range_preset: CLI > file > LAST_WORKING_DAY
    resolved_preset: RangePreset
    if range_preset is not None:
        resolved_preset = range_preset
    elif "range" in file_data:
        try:
            resolved_preset = RangePreset(str(file_data["range"]))
        except ValueError as exc:
            raise ConfigError(f"Invalid range preset: {file_data['range']!r}") from exc
    else:
        resolved_preset = RangePreset.LAST_WORKING_DAY

    # output_format: CLI > file > TEXT
    resolved_format: OutputFormat
    if output_format is not None:
        resolved_format = output_format
    elif "format" in file_data:
        try:
            resolved_format = OutputFormat(str(file_data["format"]))
        except ValueError as exc:
            raise ConfigError(f"Invalid output format: {file_data['format']!r}") from exc
    else:
        resolved_format = OutputFormat.TEXT

    # include_merges: CLI > file > False
    resolved_include_merges: bool = include_merges
    if not resolved_include_merges and "include_merges" in file_data:
        raw_im = file_data["include_merges"]
        if not isinstance(raw_im, bool):
            raise ConfigError("'include_merges' must be a boolean")
        resolved_include_merges = raw_im

    # verbose: CLI > file > False
    resolved_verbose: bool = verbose
    if not resolved_verbose and "verbose" in file_data:
        raw_v = file_data["verbose"]
        if not isinstance(raw_v, bool):
            raise ConfigError("'verbose' must be a boolean")
        resolved_verbose = raw_v

    return Config(
        repos=resolved_repos,
        scan_dirs=resolved_scan_dirs,
        author=resolved_author,
        all_authors=resolved_all_authors,
        range_preset=resolved_preset,
        since=since,
        until=until,
        output_format=resolved_format,
        include_merges=resolved_include_merges,
        verbose=resolved_verbose,
    )
