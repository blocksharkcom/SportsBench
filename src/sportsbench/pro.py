"""SportsBench Pro — the paid layer (open-core).

The free package is fully functional with your own keys and data. Pro unlocks the
*convenience* we host on modelfights.com, billed there, not here:

  • live  — managed fixtures + real odds, no third-party keys, 45+ leagues
  • run   — hosted model runs: we execute the models server-side (no LLM keys needed)
  • publish — push your leaderboard to a shareable public page on modelfights.com

Get a key: https://modelfights.com/sportsbench

This module is open source on purpose. It does nothing without a valid key + the
hosted endpoints, so the code stays MIT while the service stays monetised.
"""
from __future__ import annotations

from typing import Optional

from .config import Config
from .types import Fixture, Result
from .sources.base import FixtureSource

UPSELL = (
    "This is a SportsBench Pro feature.\n"
    "  Pro gives you managed live fixtures + odds, hosted model runs (no LLM keys "
    "needed), and a shareable public leaderboard.\n"
    "  → Get a key at https://modelfights.com/sportsbench, then set SPORTSBENCH_API_KEY."
)


class ProError(RuntimeError):
    pass


class NeedsPro(ProError):
    """Raised when a Pro command is used without a key — carries the upsell copy."""
    def __init__(self, message: str = UPSELL):
        super().__init__(message)


class ProClient:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.key = self.config.pro.api_key()
        self.base = self.config.pro.base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def require(self) -> "ProClient":
        if not self.enabled:
            raise NeedsPro()
        return self

    def _get(self, path: str, params: dict | None = None) -> dict:
        self.require()
        import httpx
        r = httpx.get(f"{self.base}{path}", params=params or {},
                      headers={"Authorization": f"Bearer {self.key}"}, timeout=40)
        if r.status_code in (401, 402, 403):
            raise ProError(f"Pro key rejected ({r.status_code}). Check your plan at "
                           f"https://modelfights.com/sportsbench")
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        self.require()
        import httpx
        r = httpx.post(f"{self.base}{path}", json=body,
                       headers={"Authorization": f"Bearer {self.key}"}, timeout=120)
        if r.status_code in (401, 402, 403):
            raise ProError(f"Pro key rejected ({r.status_code}). Check your plan at "
                           f"https://modelfights.com/sportsbench")
        r.raise_for_status()
        return r.json()

    # ---- hosted capabilities (endpoints served by modelfights.com) ----
    def live_fixtures(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        data = self._get("/sportsbench/fixtures", {"league": league or "", "limit": limit})
        return [Fixture.from_dict(d) for d in data.get("fixtures", [])]

    def live_results(self, fixture_ids: list[str]) -> dict[str, Result]:
        data = self._get("/sportsbench/results", {"ids": ",".join(fixture_ids)})
        return {str(d["fixture_id"]): Result(str(d["fixture_id"]),
                int(d["home_score"]), int(d["away_score"]))
                for d in data.get("results", [])}

    def run_hosted(self, fixtures: list[Fixture], models: list[str]) -> dict:
        """We run the models for you (no LLM keys needed); billed as compute."""
        return self._post("/sportsbench/run", {
            "models": models,
            "fixtures": [f.to_dict() for f in fixtures],
        })

    def publish(self, leaderboard: dict, title: str = "") -> str:
        """Push a leaderboard to a public page; returns its shareable URL."""
        data = self._post("/sportsbench/publish", {"title": title, "leaderboard": leaderboard})
        return data.get("url", "https://modelfights.com")


class ProLiveSource(FixtureSource):
    """Expose Pro live data through the normal source interface."""
    name = "pro-live"

    def __init__(self, client: Optional[ProClient] = None):
        self.client = (client or ProClient()).require()

    def upcoming(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        return self.client.live_fixtures(league, limit)

    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        return self.client.live_results(fixture_ids)
