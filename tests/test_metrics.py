from sportsbench.grading.metrics import brier_multiclass, log_loss, score_predictions
from sportsbench.types import Prediction, Result, Fixture, Odds


def test_brier_perfect_vs_worst():
    perfect = brier_multiclass({"home": 1.0, "draw": 0.0, "away": 0.0}, "home")
    worst = brier_multiclass({"home": 0.0, "draw": 0.0, "away": 1.0}, "home")
    assert abs(perfect) < 1e-9
    assert abs(worst - 2.0) < 1e-9


def test_log_loss_monotonic():
    assert log_loss({"home": 0.9}, "home") < log_loss({"home": 0.5}, "home")


def test_score_roundtrip():
    preds = [
        Prediction("f1", "A", "openai", "home",
                   {"home": 0.6, "draw": 0.25, "away": 0.15}, 0.6,
                   odds_at_pick={"home": 2.0, "draw": 3.4, "away": 5.0}),
        Prediction("f1", "B", "x", "away",
                   {"home": 0.2, "draw": 0.3, "away": 0.5}, 0.5,
                   odds_at_pick={"home": 2.0, "draw": 3.4, "away": 5.0}),
        # a recorded error — must not crash, must count as an error not a loss
        Prediction("f1", "C", "y", "", {"home": 0, "draw": 0, "away": 0}, 0.0,
                   error="ProviderError: 402"),
    ]
    results = {"f1": Result("f1", 2, 0)}  # home win
    scores = {s.model: s for s in score_predictions(preds, results)}
    assert scores["A"].won == 1 and scores["A"].settled == 1
    assert scores["B"].won == 0 and scores["B"].settled == 1
    assert scores["C"].errors == 1 and scores["C"].settled == 0
    # A backed home @2.0 and won -> +1 unit profit
    assert abs(scores["A"].units - 1.0) < 1e-9
    # B backed away @5.0 and lost -> -1 unit
    assert abs(scores["B"].units + 1.0) < 1e-9


def test_clv_uses_fixture_closing():
    preds = [Prediction("f1", "A", "o", "home",
                        {"home": 0.5, "draw": 0.3, "away": 0.2}, 0.5,
                        odds_at_pick={"home": 2.2, "draw": 3.4, "away": 4.0})]
    fx = {"f1": Fixture("f1", "football", "L", "H", "A", "2026-01-01",
                        closing_odds=Odds(home=2.0, draw=3.4, away=4.0))}
    scores = score_predictions(preds, {"f1": Result("f1", 1, 0)}, fixtures=fx)
    assert scores[0].avg_clv is not None and scores[0].avg_clv > 0  # beat the close
