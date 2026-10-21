"""Odds and staking math — the quant layer bettors actually care about.

All functions are pure and unit-tested. Decimal (European) odds throughout.
"""
from __future__ import annotations

from typing import Optional


def implied_prob(decimal_odds: float) -> float:
    """Convert a single decimal price to its raw implied probability."""
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be > 1.0")
    return 1.0 / decimal_odds


def devig(prices: dict[str, float], method: str = "multiplicative") -> dict[str, float]:
    """Remove the bookmaker margin so probabilities sum to 1.

    method:
      - "multiplicative": simple normalisation (fast, standard).
      - "power":          solves for k so sum(p_i**k) == 1 (handles favourite-longshot bias).
    """
    raw = {k: implied_prob(v) for k, v in prices.items()}
    if method == "multiplicative":
        total = sum(raw.values())
        return {k: v / total for k, v in raw.items()}
    if method == "power":
        lo, hi = 0.5, 2.0
        for _ in range(60):  # bisection on the exponent
            k = (lo + hi) / 2
            s = sum(p ** k for p in raw.values())
            if s > 1.0:
                lo = k
            else:
                hi = k
        k = (lo + hi) / 2
        powed = {key: p ** k for key, p in raw.items()}
        total = sum(powed.values())
        return {key: v / total for key, v in powed.items()}
    raise ValueError(f"unknown devig method: {method}")


def edge(model_prob: float, decimal_odds: float) -> float:
    """Expected value per 1 unit staked. Positive == value bet.

    EV = p * (odds - 1) - (1 - p)  ==  p * odds - 1
    """
    return model_prob * decimal_odds - 1.0


def kelly(model_prob: float, decimal_odds: float, fraction: float = 1.0) -> float:
    """Kelly stake as a fraction of bankroll (clamped at 0 — never stake on -EV).

    f* = (b*p - q) / b, where b = odds - 1, q = 1 - p. `fraction` scales it
    (0.25 == quarter-Kelly, the sane default most pros use).
    """
    b = decimal_odds - 1.0
    q = 1.0 - model_prob
    f = (b * model_prob - q) / b
    return max(0.0, f * fraction)


def no_vig_fair_odds(prices: dict[str, float], method: str = "multiplicative") -> dict[str, float]:
    """The 'fair' decimal odds once the margin is stripped out."""
    fair = devig(prices, method)
    return {k: (1.0 / p if p > 0 else float("inf")) for k, p in fair.items()}


def clv(odds_at_pick: float, closing_odds: float) -> Optional[float]:
    """Closing-line value, in probability terms.

    Positive == you took a better price than the market closed at (the sharp signal).
    Returns None if either price is missing.
    """
    if not odds_at_pick or not closing_odds or odds_at_pick <= 1.0 or closing_odds <= 1.0:
        return None
    return implied_prob(closing_odds) - implied_prob(odds_at_pick)
