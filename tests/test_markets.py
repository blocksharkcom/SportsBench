from sportsbench.markets import get_market, parse_spec, markets_for_sport
from sportsbench.types import Result


def _res(h, a, **stats):
    s = {}
    if stats:
        s = {"home": {k: v[0] for k, v in stats.items()},
             "away": {k: v[1] for k, v in stats.items()}}
    return Result("f", h, a, stats=s)


def test_parse_spec():
    assert parse_spec("1x2") == ("1x2", None)
    assert parse_spec("ou_goals@2.5") == ("ou_goals", 2.5)
    assert parse_spec("spread@-1.5") == ("spread", -1.5)


def test_1x2_settles():
    m = get_market("1x2")
    assert m.settle(_res(2, 0)) == "home"
    assert m.settle(_res(1, 1)) == "draw"
    assert m.settle(_res(0, 2)) == "away"
    assert m.selection_keys() == ["home", "draw", "away"]


def test_ou_goals():
    m = get_market("ou_goals@2.5")
    assert m.settle(_res(2, 1)) == "over"   # 3 goals
    assert m.settle(_res(1, 1)) == "under"  # 2 goals
    assert m.line == 2.5


def test_btts():
    m = get_market("btts")
    assert m.settle(_res(1, 2)) == "yes"
    assert m.settle(_res(3, 0)) == "no"


def test_dnb_voids_on_draw():
    m = get_market("dnb")
    assert m.settle(_res(2, 1)) == "home"
    assert m.settle(_res(1, 1)) is None     # void


def test_correct_score_and_other():
    m = get_market("correct_score")
    assert m.settle(_res(2, 1)) == "2-1"
    assert m.settle(_res(7, 0)) == "other"  # outside the grid


def test_ou_corners_uses_stats():
    m = get_market("ou_corners@9.5")
    assert m.settle(_res(1, 0, corners=(6, 5))) == "over"   # 11 corners
    assert m.settle(_res(1, 0, corners=(3, 4))) == "under"  # 7 corners


def test_catalog_by_sport():
    assert "1x2" in markets_for_sport("football")
    assert any(x.startswith("ou_aces") for x in markets_for_sport("tennis"))
