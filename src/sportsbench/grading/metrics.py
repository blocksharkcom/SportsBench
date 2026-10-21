"""Grading metrics — how we judge a model honestly, losses included.

Accuracy flatters favourites; the metrics that actually matter are calibration
(Brier, log loss, ECE) and money (ROI, units, CLV). All pure, all tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import log
from typing import Optional

from ..types import OUTCOMES, Prediction, Result, Fixture
from ..odds import clv as _clv
from ..markets import get_market

_EPS = 1e-15


def brier_multiclass(probs: dict[str, float], actual: str, outcomes=OUTCOMES) -> float:
    """Multiclass Brier score, range 0 (perfect) .. 2 (worst)."""
    return sum((probs.get(o, 0.0) - (1.0 if o == actual else 0.0)) ** 2 for o in outcomes)


def log_loss(probs: dict[str, float], actual: str) -> float:
    """Negative log likelihood of the actual outcome (lower is better)."""
    p = min(1.0, max(_EPS, probs.get(actual, 0.0)))
    return -log(p)


@dataclass
class ModelScore:
    model: str
    provider: str = ""
    market: str = "1x2"
    settled: int = 0
    won: int = 0
    errors: int = 0
    brier_sum: float = 0.0
    logloss_sum: float = 0.0
    units: float = 0.0          # profit to flat 1-unit stakes at odds-at-pick
    staked: float = 0.0         # total staked (for ROI denominator)
    clv_sum: float = 0.0
    clv_n: int = 0
    _cal: dict = field(default_factory=dict)  # calibration bins -> [sum_conf, hits, n]

    # ---- derived ----
    @property
    def win_rate(self) -> Optional[float]:
        return round(100.0 * self.won / self.settled, 1) if self.settled else None

    @property
    def brier(self) -> Optional[float]:
        return round(self.brier_sum / self.settled, 4) if self.settled else None

    @property
    def logloss(self) -> Optional[float]:
        return round(self.logloss_sum / self.settled, 4) if self.settled else None

    @property
    def roi(self) -> Optional[float]:
        return round(100.0 * self.units / self.staked, 1) if self.staked else None

    @property
    def avg_clv(self) -> Optional[float]:
        return round(100.0 * self.clv_sum / self.clv_n, 2) if self.clv_n else None

    @property
    def ece(self) -> Optional[float]:
        """Expected Calibration Error across confidence bins (lower is better)."""
        if not self.settled:
            return None
        total = 0.0
        for conf_sum, hits, n in self._cal.values():
            if n:
                total += (n / self.settled) * abs((hits / n) - (conf_sum / n))
        return round(total, 4)

    def to_row(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "market": self.market,
            "settled": self.settled,
            "win_rate": self.win_rate,
            "brier": self.brier,
            "logloss": self.logloss,
            "roi": self.roi,
            "units": round(self.units, 2),
            "clv": self.avg_clv,
            "ece": self.ece,
            "errors": self.errors,
        }


def _bin(conf: float) -> int:
    return min(9, int(conf * 10))  # 10 bins over [0,1)


def score_predictions(
    predictions: list[Prediction],
    results: dict[str, Result],
    stake_unit: float = 1.0,
    fixtures: dict[str, Fixture] | None = None,
) -> list[ModelScore]:
    """Grade every prediction that has a known result; return per-model scores.

    Pass `fixtures` (id -> Fixture) to enable closing-line value, which needs each
    fixture's closing odds.
    """
    fixtures = fixtures or {}
    scores: dict = {}
    _market_cache: dict = {}
    for p in predictions:
        spec = p.market or "1x2"
        key = (p.model, spec)
        s = scores.setdefault(key, ModelScore(model=p.model, provider=p.provider, market=spec))
        if p.error:
            s.errors += 1
            continue
        res = results.get(p.fixture_id)
        if res is None:
            continue  # not settled yet
        mk = _market_cache.get(spec)
        if mk is None:
            try:
                mk = _market_cache.setdefault(spec, get_market(spec))
            except ValueError:
                continue  # unknown market spec — skip rather than crash
        actual = mk.settle(res)
        if actual is None:
            continue  # void (e.g. draw-no-bet on a draw)
        s.settled += 1
        won = p.pick == actual
        s.won += int(won)
        s.brier_sum += brier_multiclass(p.probs, actual, mk.selection_keys())
        s.logloss_sum += log_loss(p.probs, actual)

        # calibration bin on stated confidence in the pick
        b = _bin(p.confidence)
        conf_sum, hits, n = s._cal.get(b, (0.0, 0, 0))
        s._cal[b] = (conf_sum + p.confidence, hits + int(won), n + 1)

        # money: stake flat at the odds we had when the pick was made
        odds = (p.odds_at_pick or {}).get(p.pick)
        if odds:
            s.staked += stake_unit
            s.units += stake_unit * ((odds - 1.0) if won else -1.0)

        # closing-line value (needs the fixture's closing odds for this market)
        fx = fixtures.get(p.fixture_id)
        close = fx.closing_market_odds(spec) if fx else None
        if odds and close:
            c = _clv(odds, close.get(p.pick))
            if c is not None:
                s.clv_sum += c
                s.clv_n += 1

    return list(scores.values())
