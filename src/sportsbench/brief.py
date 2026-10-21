"""The brief: one identical, structured prompt every model answers, for a given
market. Fairness comes from sameness — no model gets extra hints. The schema is
generated from the market's selections, so the same code handles 1X2, over/under,
correct score, aces, corners… for any sport.
"""
from __future__ import annotations

import json

from .types import Fixture
from .markets import Market

SYSTEM = (
    "You are a disciplined sports forecaster. You output calibrated probabilities, "
    "not hype. You never assume a result; you reason from the information given and "
    "your own knowledge, then commit to a single pick. Respond with STRICT JSON only."
)


def build_user_prompt(fixture: Fixture, market: Market) -> str:
    keys = market.selection_keys()
    lines = [
        f"Sport: {fixture.sport}",
        f"Competition: {fixture.league}",
        f"Fixture: {fixture.home} (home) vs {fixture.away} (away)",
        f"Kickoff (UTC): {fixture.kickoff}",
        f"Market: {market.name}",
        "Selections: " + ", ".join(f"{s.key} = {s.label}" for s in market.selections),
    ]
    odds = fixture.market_odds(market.spec)
    if odds:
        lines.append(f"Market decimal odds (reference only): {json.dumps(odds)}")
    if fixture.context:
        lines.append(f"Context: {fixture.context}")

    schema_probs = ", ".join(f'"{k}": <0..1>' for k in keys)
    pick_opts = "|".join(keys)
    lines += [
        "",
        f"Give your probability for EACH selection of the '{market.name}' market.",
        "Return STRICT JSON with this exact shape and nothing else:",
        "{",
        f'  "probs": {{ {schema_probs} }},   // must sum to ~1.0 across the selections',
        f'  "pick": "{pick_opts if len(pick_opts) < 120 else "<one selection key>"}",',
        '  "confidence": <0..1>,              // your confidence in that pick',
        '  "rationale": "<= 40 words, the key reason"',
        "}",
    ]
    return "\n".join(lines)


def normalise_probs(probs: dict, selection_keys: list) -> dict:
    """Clamp to the market's selections and renormalise to sum 1."""
    vals = {k: max(0.0, float(probs.get(k, 0.0))) for k in selection_keys}
    total = sum(vals.values()) or 1.0
    return {k: v / total for k, v in vals.items()}
