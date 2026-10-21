"""Consensus + value bets — the part a bettor opens first.

Consensus = average the models into one ensemble probability. A value bet is where
the consensus (or a single model) assigns more probability than the bookmaker's
fair line implies, i.e. positive expected value.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .brief import market_for
from .odds import edge, kelly, devig
from .types import Fixture, Prediction


@dataclass
class ValueBet:
    fixture_id: str
    fixture: str
    pick: str
    source: str            # "consensus" or a model name
    model_prob: float
    fair_prob: float       # de-vigged market probability
    decimal_odds: float
    edge: float            # expected value per unit
    kelly: float           # suggested stake fraction (scaled)

    def to_dict(self) -> dict:
        return asdict(self)


def consensus(preds_for_fixture: list[Prediction], market: list[str]) -> dict[str, float]:
    good = [p for p in preds_for_fixture if not p.error and p.probs]
    if not good:
        return {m: 0.0 for m in market}
    out = {m: sum(p.probs.get(m, 0.0) for p in good) / len(good) for m in market}
    total = sum(out.values()) or 1.0
    return {m: v / total for m, v in out.items()}


def find_value(
    fixtures: list[Fixture],
    predictions: list[Prediction],
    min_edge: float = 0.05,
    kelly_fraction: float = 0.25,
    devig_method: str = "multiplicative",
    source: str = "consensus",
    max_odds: float = 15.0,
    min_abs_edge: float = 0.02,
    min_prob: float = 0.05,
) -> list[ValueBet]:
    """Surface +EV bets, with guards against the longshot trap: a tiny model
    probability on huge odds can show a massive EV ratio that's really just noise.
    We require a reasonable price (``max_odds``), a minimum model probability, and
    a real *absolute* probability edge over the fair line — not just EV ratio."""
    by_fixture: dict[str, list[Prediction]] = {}
    for p in predictions:
        by_fixture.setdefault(p.fixture_id, []).append(p)

    bets: list[ValueBet] = []
    for fx in fixtures:
        if not fx.odds:
            continue
        market = market_for(fx)
        prices = {m: fx.odds.price(m) for m in market if fx.odds.price(m)}
        if len(prices) < 2:
            continue
        fair = devig(prices, devig_method)
        preds = by_fixture.get(fx.id, [])

        candidates: list[tuple[str, dict[str, float]]] = []
        if source == "consensus":
            candidates.append(("consensus", consensus(preds, market)))
        else:
            for p in preds:
                if not p.error and p.model == source:
                    candidates.append((p.model, p.probs))

        for src, probs in candidates:
            for m in market:
                price = prices.get(m)
                if not price or price > max_odds:
                    continue
                model_p = probs.get(m, 0.0)
                if model_p < min_prob:
                    continue
                if (model_p - fair.get(m, 0.0)) < min_abs_edge:
                    continue
                ev = edge(model_p, price)
                if ev >= min_edge:
                    bets.append(ValueBet(
                        fixture_id=fx.id, fixture=fx.label(), pick=m, source=src,
                        model_prob=round(probs.get(m, 0.0), 4),
                        fair_prob=round(fair.get(m, 0.0), 4),
                        decimal_odds=price, edge=round(ev, 4),
                        kelly=round(kelly(probs.get(m, 0.0), price, kelly_fraction), 4),
                    ))
    bets.sort(key=lambda b: b.edge, reverse=True)
    return bets
