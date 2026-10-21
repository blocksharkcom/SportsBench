"""Bundled sample + bring-your-own JSON/CSV. Zero network, zero keys — this is
what powers `sportsbench backtest --demo`, the 10-second first-run experience.
"""
from __future__ import annotations

import csv
import json
from importlib import resources
from pathlib import Path
from typing import Optional

from ..types import Fixture, Result, Odds
from .base import FixtureSource


class JSONSource(FixtureSource):
    name = "json"

    def __init__(self, fixtures_path: str, results_path: Optional[str] = None):
        self._fixtures = [Fixture.from_dict(d) for d in _read_json(fixtures_path)]
        self._results: dict[str, Result] = {}
        if results_path:
            for d in _read_json(results_path):
                self._results[str(d["fixture_id"])] = Result(
                    fixture_id=str(d["fixture_id"]),
                    home_score=int(d["home_score"]),
                    away_score=int(d["away_score"]),
                )

    def upcoming(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        fx = [f for f in self._fixtures if not league or f.league == league]
        return fx[:limit]

    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        return {fid: self._results[fid] for fid in fixture_ids if fid in self._results}


class DemoSource(JSONSource):
    """The sample dataset shipped inside the package."""
    name = "demo"

    def __init__(self):
        with resources.as_file(resources.files("sportsbench.data")) as d:
            super().__init__(str(d / "demo_fixtures.json"), str(d / "demo_results.json"))


def _read_json(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def read_fixtures_csv(path: str) -> list[Fixture]:
    """CSV columns: id,sport,league,home,away,kickoff,home_odds,away_odds,draw_odds,context"""
    out: list[Fixture] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            odds = None
            if row.get("home_odds") and row.get("away_odds"):
                odds = Odds(
                    home=float(row["home_odds"]),
                    away=float(row["away_odds"]),
                    draw=float(row["draw_odds"]) if row.get("draw_odds") else None,
                )
            out.append(Fixture(
                id=row["id"], sport=row.get("sport", "football"),
                league=row.get("league", ""), home=row["home"], away=row["away"],
                kickoff=row.get("kickoff", ""), odds=odds, context=row.get("context", ""),
            ))
    return out
