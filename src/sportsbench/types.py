"""Core data types for SportsBench.

Deliberately dependency-light: plain dataclasses, JSON-serialisable, so the
package installs small and runs anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import datetime as _dt

Outcome = str  # one of: "home", "draw", "away"
OUTCOMES: tuple[str, str, str] = ("home", "draw", "away")


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Odds:
    """Decimal (European) odds for the three-way market."""

    home: float
    away: float
    draw: Optional[float] = None  # None for two-way sports (tennis, etc.)

    def implied(self) -> dict[str, float]:
        """Raw implied probabilities (still contain the bookmaker margin)."""
        raw = {"home": 1.0 / self.home, "away": 1.0 / self.away}
        if self.draw is not None:
            raw["draw"] = 1.0 / self.draw
        return raw

    def fair(self) -> dict[str, float]:
        """Margin-removed ('de-vigged') probabilities that sum to 1."""
        raw = self.implied()
        total = sum(raw.values())
        return {k: v / total for k, v in raw.items()}

    def margin(self) -> float:
        """Bookmaker overround, e.g. 0.05 == a 5% margin."""
        return sum(self.implied().values()) - 1.0

    def price(self, pick: str) -> Optional[float]:
        return getattr(self, pick, None)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Fixture:
    id: str
    sport: str
    league: str
    home: str
    away: str
    kickoff: str  # ISO 8601
    status: str = "scheduled"  # scheduled | live | finished
    odds: Optional[Odds] = None            # odds at the time predictions are made
    closing_odds: Optional[Odds] = None    # odds at kickoff (for closing-line value)
    context: str = ""  # optional free-text brief: form, injuries, venue, weather…

    def label(self) -> str:
        return f"{self.home} vs {self.away}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["odds"] = self.odds.to_dict() if self.odds else None
        d["closing_odds"] = self.closing_odds.to_dict() if self.closing_odds else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Fixture":
        odds = d.get("odds")
        closing = d.get("closing_odds")
        return cls(
            id=str(d["id"]),
            sport=d.get("sport", "football"),
            league=d.get("league", ""),
            home=d["home"],
            away=d["away"],
            kickoff=d.get("kickoff", _now_iso()),
            status=d.get("status", "scheduled"),
            odds=Odds(**odds) if odds else None,
            closing_odds=Odds(**closing) if closing else None,
            context=d.get("context", ""),
        )


@dataclass
class Prediction:
    fixture_id: str
    model: str                 # display name, e.g. "GPT-5"
    provider: str              # e.g. "openai"
    pick: Outcome
    probs: dict[str, float]    # probabilities over OUTCOMES, should sum ~1
    confidence: float          # 0..1, the model's own stated confidence in `pick`
    rationale: str = ""
    odds_at_pick: Optional[dict] = None   # snapshot of Odds.to_dict() at pick time
    created_at: str = field(default_factory=_now_iso)
    prompt_sha256: str = ""    # proof the brief was fixed before kickoff
    error: Optional[str] = None  # set when the model call failed (recorded, not hidden)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Prediction":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


@dataclass
class Result:
    fixture_id: str
    home_score: int
    away_score: int

    @property
    def outcome(self) -> Outcome:
        if self.home_score > self.away_score:
            return "home"
        if self.home_score < self.away_score:
            return "away"
        return "draw"

    def to_dict(self) -> dict:
        return asdict(self)
