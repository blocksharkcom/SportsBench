"""football-data.org — a genuinely free fixtures/results feed (free tier key).

Note: the free tier does NOT include odds. Add odds via your own CSV/JSON, or
use the Pro live feed (modelfights.com) which bundles managed odds. Get a free
key at https://www.football-data.org/client/register
"""
from __future__ import annotations

import os
import httpx

from ..types import Fixture, Result, Odds
from .base import FixtureSource

BASE = "https://api.football-data.org/v4"

# a few common competition codes for convenience
LEAGUES = {
    "epl": "PL", "premier-league": "PL", "laliga": "PD", "seriea": "SA",
    "bundesliga": "BL1", "ligue1": "FL1", "ucl": "CL", "championship": "ELC",
}


class FootballDataSource(FixtureSource):
    name = "football-data.org"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "set FOOTBALL_DATA_API_KEY (free at football-data.org/client/register)"
            )

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = httpx.get(f"{BASE}{path}", params=params or {},
                      headers={"X-Auth-Token": self.api_key}, timeout=30)
        r.raise_for_status()
        return r.json()

    def upcoming(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        code = LEAGUES.get((league or "").lower(), league or "PL")
        data = self._get(f"/competitions/{code}/matches", {"status": "SCHEDULED"})
        out: list[Fixture] = []
        for m in data.get("matches", [])[:limit]:
            out.append(Fixture(
                id=str(m["id"]), sport="football",
                league=m.get("competition", {}).get("name", code),
                home=m["homeTeam"]["name"], away=m["awayTeam"]["name"],
                kickoff=m["utcDate"], status="scheduled",
                odds=_parse_odds(m.get("odds")),
            ))
        return out

    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        out: dict[str, Result] = {}
        for fid in fixture_ids:
            try:
                m = self._get(f"/matches/{fid}").get("match") or self._get(f"/matches/{fid}")
                ft = (m.get("score", {}) or {}).get("fullTime", {})
                if ft.get("home") is not None and ft.get("away") is not None:
                    out[fid] = Result(fid, int(ft["home"]), int(ft["away"]))
            except Exception:
                continue
        return out


def _parse_odds(odds: dict | None) -> Odds | None:
    if not odds:
        return None
    h, a, d = odds.get("homeWin"), odds.get("awayWin"), odds.get("draw")
    if h and a:
        return Odds(home=float(h), away=float(a), draw=float(d) if d else None)
    return None
