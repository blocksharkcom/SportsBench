"""Consensus + value bets — the part a bettor opens first. Works for any market.

Consensus = average the models into one ensemble probability over the market's
selections. A value bet is where the consensus (or one model) assigns more
probability than the bookmaker's fair line implies, i.e. positive expected value.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .markets import get_market
from .odds import edge, kelly, devig
from .types import Fixture, Prediction


@dataclass
class ValueBet:
    fixture_id: str
    fixture: str
    market: str
    pick: str
    label: str             # human label for the selection
    source: str            # "consensus" or a model name
    model_prob: float
    fair_prob: float       # de-vigged market probability
    decimal_odds: float
    edge: float            # expected value per unit
    kelly: float           # suggested stake fraction (scaled)

    def to_dict(self) -> dict:
        return asdict(self)


def consensus(preds_for_fixture: list, keys: list) -> dict:
    good = [p for p in preds_for_fixture if not p.error and p.probs]
    if not good:
        return {k: 0.0 for k in keys}
    out = {k: sum(p.probs.get(k, 0.0) for p in good) / len(good) for k in keys}
    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def find_value(
    fixtures: list,
    predictions: list,
    market: str = "1x2",
    min_edge: float = 0.05,
    kelly_fraction: float = 0.25,
    devig_method: str = "multiplicative",
    source: str = "consensus",
    max_odds: float = 15.0,
    min_abs_edge: float = 0.02,
    min_prob: float = 0.05,
) -> list:
    """Surface +EV bets for a single market, with guards against the longshot trap."""
    mk = get_market(market)
    keys = mk.selection_keys()
    by_fixture: dict = {}
    for p in predictions:
        if (p.market or "1x2") == market:
            by_fixture.setdefault(p.fixture_id, []).append(p)

    bets: list = []
    for fx in fixtures:
        odds = fx.market_odds(market)
        if not odds:
            continue
        prices = {k: odds[k] for k in keys if odds.get(k) and odds[k] > 1.0}
        if len(prices) < 2:
            continue
        fair = devig(prices, devig_method)
        preds = by_fixture.get(fx.id, [])

        candidates = []
        if source == "consensus":
            candidates.append(("consensus", consensus(preds, keys)))
        else:
            for p in preds:
                if not p.error and p.model == source:
                    candidates.append((p.model, p.probs))

        for src, probs in candidates:
            for k in keys:
                price = prices.get(k)
                if not price or price > max_odds:
                    continue
                model_p = probs.get(k, 0.0)
                if model_p < min_prob or (model_p - fair.get(k, 0.0)) < min_abs_edge:
                    continue
                ev = edge(model_p, price)
                if ev >= min_edge:
                    bets.append(ValueBet(
                        fixture_id=fx.id, fixture=fx.label(), market=market, pick=k,
                        label=mk.label_for(k), source=src,
                        model_prob=round(model_p, 4), fair_prob=round(fair.get(k, 0.0), 4),
                        decimal_odds=price, edge=round(ev, 4),
                        kelly=round(kelly(model_p, price, kelly_fraction), 4),
                    ))
    bets.sort(key=lambda b: b.edge, reverse=True)
    return bets
