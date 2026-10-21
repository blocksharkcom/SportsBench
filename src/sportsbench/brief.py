"""The brief: one identical, structured prompt every model answers. Fairness
comes from sameness — no model gets extra hints.
"""
from __future__ import annotations

import json
from .types import Fixture

SYSTEM = (
    "You are a disciplined sports forecaster. You output calibrated probabilities, "
    "not hype. You never assume a result; you reason from the information given and "
    "your own knowledge, then commit to a single pick. Respond with STRICT JSON only."
)

_TWO_WAY = {"tennis", "basketball", "baseball", "nfl", "mma", "boxing"}


def _market(fixture: Fixture) -> list[str]:
    return ["home", "away"] if fixture.sport in _TWO_WAY else ["home", "draw", "away"]


def build_user_prompt(fixture: Fixture) -> str:
    market = _market(fixture)
    lines = [
        f"Sport: {fixture.sport}",
        f"Competition: {fixture.league}",
        f"Fixture: {fixture.home} (home) vs {fixture.away} (away)",
        f"Kickoff (UTC): {fixture.kickoff}",
    ]
    if fixture.odds:
        prices = {k: v for k, v in fixture.odds.to_dict().items()}
        lines.append(f"Market decimal odds (for reference only): {json.dumps(prices)}")
    if fixture.context:
        lines.append(f"Context: {fixture.context}")

    schema_probs = ", ".join(f'"{m}": <0..1>' for m in market)
    pick_opts = "|".join(market)
    lines += [
        "",
        "Return STRICT JSON with this exact shape and nothing else:",
        "{",
        f'  "probs": {{ {schema_probs} }},   // must sum to ~1.0',
        f'  "pick": "{pick_opts}",            // your single best call',
        '  "confidence": <0..1>,              // your confidence in that pick',
        '  "rationale": "<= 40 words, the key reason"',
        "}",
    ]
    return "\n".join(lines)


def normalise_probs(probs: dict, market: list[str]) -> dict[str, float]:
    """Clamp to the market outcomes and renormalise to sum 1."""
    vals = {m: max(0.0, float(probs.get(m, 0.0))) for m in market}
    total = sum(vals.values()) or 1.0
    return {m: v / total for m, v in vals.items()}


def market_for(fixture: Fixture) -> list[str]:
    return _market(fixture)
