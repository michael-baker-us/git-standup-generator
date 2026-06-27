"""Tests for config.py — load_config, TOML parsing, precedence, validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from standup_generator.config import OutputFormat, load_config
from standup_generator.errors import ConfigError
from standup_generator.timerange import RangePreset


def test_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No config file, no CLI args → all defaults."""
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.repos == (Path.cwd(),)
    assert config.author is None
    assert config.all_authors is False
    assert config.range_preset is RangePreset.LAST_WORKING_DAY
    assert config.since is None
    assert config.until is None
    assert config.output_format is OutputFormat.TEXT
    assert config.include_merges is False
    assert config.verbose is False


def test_toml_repos_and_format(tmp_path: Path) -> None:
    """TOML file sets repos (with tilde expansion) and format."""
    cfg = tmp_path / "standup.toml"
    cfg.write_text('[placeholder]\nrepos = ["~/code/api"]\nformat = "markdown"\n', encoding="utf-8")
    # Rewrite without placeholder section
    cfg.write_text('repos = ["~/code/api"]\nformat = "markdown"\n', encoding="utf-8")
    config = load_config(config_path=cfg)
    assert config.output_format is OutputFormat.MARKDOWN
    assert len(config.repos) == 1
    assert config.repos[0] == Path("~/code/api").expanduser()


def test_tilde_expansion(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('repos = ["~/projects/myrepo"]\n', encoding="utf-8")
    config = load_config(config_path=cfg)
    assert not str(config.repos[0]).startswith("~")
    assert config.repos[0] == Path.home() / "projects" / "myrepo"


def test_unknown_key_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text("banana = true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown config keys"):
        load_config(config_path=cfg)


def test_cli_author_overrides_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('author = "from-file@example.com"\n', encoding="utf-8")
    config = load_config(author="cli@example.com", config_path=cfg)
    assert config.author == "cli@example.com"


def test_file_author_used_when_no_cli(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('author = "file@example.com"\n', encoding="utf-8")
    config = load_config(config_path=cfg)
    assert config.author == "file@example.com"


def test_range_preset_from_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('range = "week"\n', encoding="utf-8")
    config = load_config(config_path=cfg)
    assert config.range_preset is RangePreset.WEEK


def test_cli_range_overrides_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('range = "week"\n', encoding="utf-8")
    config = load_config(range_preset=RangePreset.TODAY, config_path=cfg)
    assert config.range_preset is RangePreset.TODAY


def test_invalid_range_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('range = "not-a-range"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid range preset"):
        load_config(config_path=cfg)


def test_invalid_format_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('format = "html"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid output format"):
        load_config(config_path=cfg)


def test_include_merges_from_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text("include_merges = true\n", encoding="utf-8")
    config = load_config(config_path=cfg)
    assert config.include_merges is True


def test_cli_include_merges_overrides_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text("include_merges = false\n", encoding="utf-8")
    config = load_config(include_merges=True, config_path=cfg)
    assert config.include_merges is True


def test_all_authors_from_file(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text("all_authors = true\n", encoding="utf-8")
    config = load_config(config_path=cfg)
    assert config.all_authors is True


def test_local_standup_toml_auto_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.standup.toml` in CWD is discovered without explicit --config."""
    toml = tmp_path / ".standup.toml"
    toml.write_text('format = "markdown"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.output_format is OutputFormat.MARKDOWN


def test_explicit_config_path_wins_over_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit config_path wins over local .standup.toml."""
    local = tmp_path / ".standup.toml"
    local.write_text('format = "markdown"\n', encoding="utf-8")
    explicit = tmp_path / "custom.toml"
    explicit.write_text('format = "text"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = load_config(config_path=explicit)
    assert config.output_format is OutputFormat.TEXT


def test_repos_not_a_list_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "standup.toml"
    cfg.write_text('repos = "not-a-list"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="'repos' must be a list"):
        load_config(config_path=cfg)


def test_config_is_frozen() -> None:
    config = load_config()
    with pytest.raises((AttributeError, TypeError)):
        config.verbose = True  # type: ignore[misc]
