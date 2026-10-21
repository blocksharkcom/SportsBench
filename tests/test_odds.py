from sportsbench.odds import implied_prob, devig, edge, kelly, clv
from sportsbench.types import Odds


def test_implied_prob():
    assert abs(implied_prob(2.0) - 0.5) < 1e-9
    assert abs(implied_prob(4.0) - 0.25) < 1e-9


def test_devig_sums_to_one():
    prices = {"home": 2.1, "draw": 3.4, "away": 3.9}
    fair = devig(prices)
    assert abs(sum(fair.values()) - 1.0) < 1e-9
    # de-vigged probabilities are lower than raw implied (margin removed)
    assert fair["home"] < implied_prob(prices["home"])


def test_devig_power_sums_to_one():
    prices = {"home": 1.5, "away": 2.7}
    fair = devig(prices, method="power")
    assert abs(sum(fair.values()) - 1.0) < 1e-6


def test_edge_sign():
    assert edge(0.60, 2.0) > 0      # 60% at even money is +EV
    assert edge(0.40, 2.0) < 0      # 40% at even money is -EV


def test_kelly_never_negative():
    assert kelly(0.40, 2.0) == 0.0          # no stake on -EV
    assert 0 < kelly(0.60, 2.0) <= 1.0      # positive, bounded
    assert kelly(0.60, 2.0, fraction=0.25) < kelly(0.60, 2.0)  # fractional is smaller


def test_clv():
    # took 2.2, closed 2.0 -> positive CLV (beat the closing line)
    assert clv(2.2, 2.0) > 0
    assert clv(2.0, 2.2) < 0
    assert clv(2.0, None) is None


def test_odds_margin_and_fair():
    o = Odds(home=2.0, draw=3.5, away=4.0)
    assert o.margin() > 0
    assert abs(sum(o.fair().values()) - 1.0) < 1e-9
