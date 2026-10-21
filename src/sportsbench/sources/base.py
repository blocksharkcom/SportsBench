"""Fixture/result sources. Implement two methods and you've added a data feed."""
from __future__ import annotations

from abc import ABC, abstractmethod
from ..types import Fixture, Result


class FixtureSource(ABC):
    name = "base"

    @abstractmethod
    def upcoming(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        ...

    @abstractmethod
    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        ...
