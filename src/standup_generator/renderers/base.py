from __future__ import annotations

from typing import Protocol

from standup_generator.models import StandupReport


class Renderer(Protocol):
    def render(self, report: StandupReport) -> str: ...
