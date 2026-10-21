"""Client for modelfights.com — the easiest way to feed SportsBench real data.

Two tiers, one key (get it at https://modelfights.com/sportsbench):

  FREE  (just sign up)      — fetch upcoming fixtures, events and results across
                              45+ leagues, with odds. No third-party data keys.
  PRO   (paid plan)         — hosted model runs (we run the models server-side, so
                              you need no LLM keys at all) and cloud publish to a
                              shareable public leaderboard.

This module is open source on purpose: it does nothing without a key + the hosted
endpoints, so the code stays MIT while the service stays monetised.
"""
from __future__ import annotations

from typing import Optional

from .config import Config
from .types import Fixture, Result
from .sources.base import FixtureSource

SIGNUP = "https://modelfights.com/sportsbench"

NEEDS_KEY = (
    "Fetching live data needs a modelfights.com API key — it's FREE, just sign up.\n"
    f"  1. Create a free account at {SIGNUP}\n"
    "  2. Copy your API key\n"
    "  3. export MODELFIGHTS_API_KEY=...   (or add it to your .env)\n"
    "Then you get upcoming fixtures, events and odds across 45+ leagues — no other keys needed."
)
NEEDS_PRO = (
    "This is a SportsBench Pro feature (hosted model runs / cloud publish).\n"
    f"  Your key works, but this needs a paid plan. Upgrade at {SIGNUP}"
)


class ProError(RuntimeError):
    pass


class NeedsKey(ProError):
    """No modelfights.com key set — but one is free."""
    def __init__(self, message: str = NEEDS_KEY):
        super().__init__(message)


class NeedsPro(ProError):
    """Key is valid but the account isn't on a paid plan for this feature."""
    def __init__(self, message: str = NEEDS_PRO):
        super().__init__(message)


class ModelFightsClient:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.key = self.config.modelfights.api_key()
        self.base = self.config.modelfights.base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def require(self) -> "ModelFightsClient":
        if not self.enabled:
            raise NeedsKey()
        return self

    def _request(self, method: str, path: str, *, params=None, body=None) -> dict:
        self.require()
        import httpx
        headers = {"Authorization": f"Bearer {self.key}"}
        timeout = 120 if method == "POST" else 40
        try:
            r = httpx.request(method, f"{self.base}{path}", params=params or {},
                              json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            raise ProError(f"request to modelfights.com failed: {e}") from e
        if r.status_code in (401, 403):
            raise NeedsKey(f"modelfights.com key rejected. Check it at {SIGNUP}")
        if r.status_code == 402:  # payment required -> needs a Pro plan
            raise NeedsPro()
        r.raise_for_status()
        return r.json()

    # ---- FREE: data (sign-up tier) ----
    def fixtures(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        data = self._request("GET", "/sportsbench/fixtures",
                             params={"league": league or "", "limit": limit})
        return [Fixture.from_dict(d) for d in data.get("fixtures", [])]

    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        data = self._request("GET", "/sportsbench/results",
                             params={"ids": ",".join(fixture_ids)})
        return {str(d["fixture_id"]): Result(str(d["fixture_id"]),
                int(d["home_score"]), int(d["away_score"]))
                for d in data.get("results", [])}

    # ---- PRO: compute (paid tier) ----
    def run_hosted(self, fixtures: list[Fixture], models: list[str]) -> dict:
        """We run the models for you (no LLM keys needed); billed as compute."""
        return self._request("POST", "/sportsbench/run",
                             body={"models": models, "fixtures": [f.to_dict() for f in fixtures]})

    def publish(self, leaderboard: dict, title: str = "") -> str:
        """Push a leaderboard to a shareable public page; returns its URL."""
        data = self._request("POST", "/sportsbench/publish",
                             body={"title": title, "leaderboard": leaderboard})
        return data.get("url", "https://modelfights.com")


# Back-compat alias
ProClient = ModelFightsClient


class ModelFightsSource(FixtureSource):
    """modelfights.com as a normal fixture source (free with a signup key)."""
    name = "modelfights"

    def __init__(self, client: Optional[ModelFightsClient] = None):
        self.client = (client or ModelFightsClient()).require()

    def upcoming(self, league: str | None = None, limit: int = 20) -> list[Fixture]:
        return self.client.fixtures(league, limit)

    def results(self, fixture_ids: list[str]) -> dict[str, Result]:
        return self.client.results(fixture_ids)


# Back-compat alias
ProLiveSource = ModelFightsSource
