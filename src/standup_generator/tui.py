"""Full-screen TUI for Git Standup Generator."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Rule,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from standup_generator.config import OutputFormat, load_config
from standup_generator.errors import StandupError
from standup_generator.timerange import RangePreset

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_RANGE_ID_TO_PRESET: dict[str, RangePreset] = {
    "rb-last-working-day": RangePreset.LAST_WORKING_DAY,
    "rb-yesterday": RangePreset.YESTERDAY,
    "rb-today": RangePreset.TODAY,
    "rb-week": RangePreset.WEEK,
    "rb-month": RangePreset.MONTH,
    "rb-quarter": RangePreset.QUARTER,
}

_PRESET_LABEL: dict[RangePreset, str] = {
    RangePreset.LAST_WORKING_DAY: "Last working day",
    RangePreset.YESTERDAY: "Yesterday",
    RangePreset.TODAY: "Today (so far)",
    RangePreset.WEEK: "Past week (7 days)",
    RangePreset.MONTH: "Past month (30 days)",
    RangePreset.QUARTER: "Past quarter (90 days)",
}

APP_CSS = """
Screen { background: $surface; }

/* ── Tabs ───────────────────────────────────────────────────── */
TabbedContent ContentSwitcher { border: none; }

/* Each tab is a vertical stack: scrollable body + pinned footer */
TabPane { padding: 0; layout: vertical; }

.tab-body {
    padding: 1 2;
    height: 1fr;   /* fills available space; scrolls when content overflows */
}

/* Pinned button row — always visible regardless of terminal height */
.tab-foot {
    padding: 0 2 1 2;
    height: auto;
}

/* ── Typography ─────────────────────────────────────────────── */
.section-title {
    text-style: bold;
    color: $text;
    padding: 1 0 0 0;
    margin-bottom: 1;
}
.hint {
    color: $text-muted;
    padding: 0 0 0 4;
    margin-bottom: 1;
}

/* ── Form ────────────────────────────────────────────────────── */
RadioSet {
    background: transparent;
    border: none;
    padding: 0;
    margin-bottom: 1;
}
.row {
    height: 3;
    align: left middle;
    margin-bottom: 1;
}
.row-label {
    width: 16;
    height: 3;
    content-align: left middle;
    color: $text-muted;
}
Input { margin-bottom: 1; }
.indent { margin-left: 4; margin-bottom: 1; }

/* ── Tab navigation buttons ─────────────────────────────────── */
.tab-nav {
    height: auto;
    align: right middle;
    padding-top: 1;
}
.btn-next { margin-left: 1; }
.btn-back { margin-right: 1; }

/* ── Generate tab ────────────────────────────────────────────── */
.preview-box {
    border: round $primary-darken-2;
    background: $surface-lighten-1;
    padding: 1 2;
    min-height: 7;
    margin-bottom: 1;
}
#generate-btn { width: 100%; margin: 1 0; }
#status-label { height: 1; color: $text-muted; }
#results-area {
    border: round $primary-darken-2;
    background: $surface-lighten-1;
    padding: 1 2;
    height: 1fr;
    overflow-y: auto;
}
"""


class StandupTUI(App[None]):
    """Git Standup Generator — interactive TUI."""

    TITLE = "Git Standup Generator"
    SUB_TITLE = "Daily commit summary"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+g", "generate", "Generate", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="source"):
            # ── Tab 1: Source ────────────────────────────────────────────────
            with TabPane("📁  Source", id="source"):
                with ScrollableContainer(classes="tab-body"):
                    yield Label("Where should I look for commits?", classes="section-title")
                    with RadioSet(id="source-type"):
                        yield RadioButton(
                            "Scan a directory for git repos", id="rb-scan", value=True
                        )
                        yield RadioButton(f"Current directory  ({Path.cwd()})", id="rb-cwd")
                        yield RadioButton("Specify repo path(s)", id="rb-repos")
                    with Vertical(id="scan-dir-group", classes="indent"):
                        yield Input(
                            value=str(Path.home() / "repos"),
                            placeholder="~/repos",
                            id="scan-dir-input",
                        )
                    with Vertical(id="repos-group", classes="indent"):
                        yield Input(
                            value=str(Path.cwd()),
                            placeholder="/path/to/repo1, /path/to/repo2",
                            id="repos-input",
                        )
                        yield Label("Comma-separated paths.", classes="hint")
                with Vertical(classes="tab-foot"):
                    yield Rule()
                    with Horizontal(classes="tab-nav"):
                        yield Button(
                            "Next: Range →",
                            id="btn-to-range",
                            variant="primary",
                            classes="btn-next",
                        )

            # ── Tab 2: Range ─────────────────────────────────────────────────
            with TabPane("📅  Range", id="range"):
                with ScrollableContainer(classes="tab-body"):
                    yield Label("Date range:", classes="section-title")
                    with RadioSet(id="range-preset"):
                        yield RadioButton("Last working day", id="rb-last-working-day", value=True)
                        yield RadioButton("Yesterday", id="rb-yesterday")
                        yield RadioButton("Today (so far)", id="rb-today")
                        yield RadioButton("Past week    (7 days)", id="rb-week")
                        yield RadioButton("Past month   (30 days)", id="rb-month")
                        yield RadioButton("Past quarter (90 days)", id="rb-quarter")
                with Vertical(classes="tab-foot"):
                    yield Rule()
                    with Horizontal(classes="tab-nav"):
                        yield Button("← Back", id="btn-to-source", classes="btn-back")
                        yield Button(
                            "Next: Options →",
                            id="btn-to-options",
                            variant="primary",
                            classes="btn-next",
                        )

            # ── Tab 3: Options ───────────────────────────────────────────────
            with TabPane("⚙️  Options", id="options"):
                with ScrollableContainer(classes="tab-body"):
                    yield Label("Output format:", classes="section-title")
                    with RadioSet(id="output-format"):
                        yield RadioButton("Text (plain)", id="rb-text", value=True)
                        yield RadioButton("Markdown", id="rb-markdown")

                    yield Label("AI narrative:", classes="section-title")
                    with Horizontal(classes="row"):
                        yield Label("Use Claude AI", classes="row-label")
                        yield Switch(id="ai-switch", value=False)
                    with Vertical(id="ai-model-group", classes="indent"):
                        yield Input(value=_DEFAULT_MODEL, id="model-input")
                        yield Label("Requires ANTHROPIC_API_KEY to be set.", classes="hint")

                    yield Label("Save to file:", classes="section-title")
                    with Horizontal(classes="row"):
                        yield Label("Save report", classes="row-label")
                        yield Switch(id="save-switch", value=False)
                    with Vertical(id="output-path-group", classes="indent"):
                        yield Input(placeholder="~/standup.md", id="output-path-input")

                with Vertical(classes="tab-foot"):
                    yield Rule()
                    with Horizontal(classes="tab-nav"):
                        yield Button("← Back", id="btn-to-range2", classes="btn-back")
                        yield Button(
                            "Review & Generate →",
                            id="btn-to-generate",
                            variant="primary",
                            classes="btn-next",
                        )

            # ── Tab 4: Generate ──────────────────────────────────────────────
            with TabPane("▶  Generate", id="generate"), Vertical(classes="tab-body"):
                yield Label("Settings summary:", classes="section-title")
                yield Static("", id="settings-preview", classes="preview-box")
                yield Label("", id="status-label")
                yield Button("  Generate Report", id="generate-btn", variant="primary")
                yield Static(
                    "[dim]Your report will appear here after generating.[/dim]",
                    id="results-area",
                )

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#repos-group").display = False
        self.query_one("#ai-model-group").display = False
        self.query_one("#output-path-group").display = False
        self._refresh_preview()

    # ── Events ───────────────────────────────────────────────────────────────

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "source-type":
            pressed_id = event.pressed.id if event.pressed else None
            self.query_one("#scan-dir-group").display = pressed_id == "rb-scan"
            self.query_one("#repos-group").display = pressed_id == "rb-repos"
        self._refresh_preview()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "ai-switch":
            self.query_one("#ai-model-group").display = event.value
        elif event.switch.id == "save-switch":
            self.query_one("#output-path-group").display = event.value
        self._refresh_preview()

    def on_input_changed(self, _: Input.Changed) -> None:
        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        tab_nav = {
            "btn-to-range": "range",
            "btn-to-source": "source",
            "btn-to-options": "options",
            "btn-to-range2": "range",
            "btn-to-generate": "generate",
        }
        if event.button.id in tab_nav:
            self.query_one(TabbedContent).active = tab_nav[event.button.id]
        elif event.button.id == "generate-btn":
            self.action_generate()

    def action_generate(self) -> None:
        try:
            params = self._collect_params()
        except Exception as exc:
            self.query_one("#results-area", Static).update(f"[bold red]Error:[/bold red] {exc}")
            self.query_one(TabbedContent).active = "generate"
            return

        self.query_one(TabbedContent).active = "generate"
        self.query_one("#results-area", Static).update("[dim]Collecting commits…[/dim]")
        self.query_one("#status-label", Label).update("")
        self.query_one("#generate-btn", Button).disabled = True
        self._generate(**params)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _collect_params(self) -> dict[str, Any]:
        pressed_src = self.query_one("#source-type", RadioSet).pressed_button
        src_id = pressed_src.id if pressed_src else "rb-scan"

        repos: tuple[Path, ...] | None = None
        scan_dirs: tuple[Path, ...] | None = None

        if src_id == "rb-scan":
            raw = self.query_one("#scan-dir-input", Input).value.strip()
            scan_dirs = (Path(raw or "~/repos").expanduser(),)
        elif src_id == "rb-repos":
            raw = self.query_one("#repos-input", Input).value.strip()
            repos = tuple(Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()) or (
                Path.cwd(),
            )
        # rb-cwd → both None → load_config defaults to CWD

        pressed_range = self.query_one("#range-preset", RadioSet).pressed_button
        range_id = (pressed_range.id or "") if pressed_range else ""
        preset = _RANGE_ID_TO_PRESET.get(range_id, RangePreset.LAST_WORKING_DAY)

        pressed_fmt = self.query_one("#output-format", RadioSet).pressed_button
        fmt = (
            OutputFormat.MARKDOWN
            if pressed_fmt and pressed_fmt.id == "rb-markdown"
            else OutputFormat.TEXT
        )

        ai: bool = self.query_one("#ai-switch", Switch).value
        model = self.query_one("#model-input", Input).value.strip() or _DEFAULT_MODEL
        save: bool = self.query_one("#save-switch", Switch).value
        out_path_raw = self.query_one("#output-path-input", Input).value.strip()

        return {
            "repos": repos,
            "scan_dirs": scan_dirs,
            "preset": preset,
            "fmt": fmt,
            "ai": ai,
            "model": model,
            "save": save,
            "out_path_raw": out_path_raw,
        }

    def _refresh_preview(self) -> None:
        try:
            p = self._collect_params()
            pressed_src = self.query_one("#source-type", RadioSet).pressed_button
            src_id = pressed_src.id if pressed_src else "rb-scan"

            if src_id == "rb-scan":
                src_val = self.query_one("#scan-dir-input", Input).value or "~/repos"
                src_str = f"Scan    {src_val}"
            elif src_id == "rb-repos":
                src_str = f"Repos   {self.query_one('#repos-input', Input).value or '(none set)'}"
            else:
                src_str = f"CWD     {Path.cwd()}"

            ai_str = f"On  ({self.query_one('#model-input', Input).value})" if p["ai"] else "Off"
            out_str = str(p["out_path_raw"]) if p["save"] and p["out_path_raw"] else "stdout"

            preview = "\n".join(
                [
                    f"  Source    {src_str}",
                    f"  Range     {_PRESET_LABEL[p['preset']]}",
                    f"  Format    {p['fmt'].value}",
                    f"  AI        {ai_str}",
                    f"  Output    {out_str}",
                ]
            )
            self.query_one("#settings-preview", Static).update(preview)
        except Exception:
            pass

    @work(thread=True)
    def _generate(
        self,
        *,
        repos: tuple[Path, ...] | None,
        scan_dirs: tuple[Path, ...] | None,
        preset: RangePreset,
        fmt: OutputFormat,
        ai: bool,
        model: str,
        save: bool,
        out_path_raw: str,
    ) -> None:
        from standup_generator.cli import run as run_pipeline
        from standup_generator.git.runner import subprocess_runner
        from standup_generator.summarizers.claude import ClaudeSummarizer
        from standup_generator.summarizers.template import TemplateSummarizer

        try:
            config = load_config(
                repos=repos,
                scan_dirs=scan_dirs,
                range_preset=preset,
                output_format=fmt,
            )
            summarizer = ClaudeSummarizer(model=model) if ai else TemplateSummarizer()
            now = datetime.now(UTC).astimezone()
            result = run_pipeline(config, now=now, runner=subprocess_runner, summarizer=summarizer)

            saved_note = ""
            if save and out_path_raw:
                out_path = Path(out_path_raw).expanduser()
                out_path.write_text(result, encoding="utf-8")
                saved_note = f"\n\n[dim]Saved to {out_path}[/dim]"

            self.call_from_thread(self._show_result, escape(result) + saved_note)

        except StandupError as exc:
            self.call_from_thread(self._show_error, str(exc))
        except Exception as exc:
            self.call_from_thread(self._show_error, f"Unexpected error: {exc}")
        finally:
            self.call_from_thread(self._done)

    def _show_result(self, result: str) -> None:
        self.query_one("#results-area", Static).update(result)
        self.query_one("#status-label", Label).update("[green]Done.[/green]")

    def _show_error(self, message: str) -> None:
        self.query_one("#results-area", Static).update(
            f"[bold red]Error:[/bold red] {escape(message)}"
        )
        self.query_one("#status-label", Label).update("[red]Failed.[/red]")

    def _done(self) -> None:
        self.query_one("#generate-btn", Button).disabled = False


def launch() -> None:
    """Entry point called from cli.main() when no source flags are given."""
    StandupTUI().run()
