"""Minimal library usage — run the bundled demo end to end, no API keys needed.

    python examples/quickstart.py
"""
from importlib import resources

import sportsbench as sb
from sportsbench.sources.files import DemoSource, _read_json
from sportsbench.types import Prediction
from sportsbench.grading import to_markdown


def main():
    # 1. fixtures + results from the bundled sample
    src = DemoSource()
    fixtures = src.upcoming(limit=500)
    fixtures_by_id = {f.id: f for f in fixtures}
    results = src.results(list(fixtures_by_id))

    # 2. the sample ships ready-made predictions so this runs offline.
    #    (For real runs: preds = sb.run_predictions(sb.Config.load(), fixtures))
    with resources.as_file(resources.files("sportsbench.data")) as d:
        preds = [Prediction.from_dict(x) for x in _read_json(str(d / "demo_predictions.json"))]

    # 3. grade + rank — a leaderboard per market
    all_scores = sb.score_predictions(preds, results, fixtures=fixtures_by_id)
    for spec in ["1x2", "ou_goals@2.5", "btts", "ou_corners@9.5"]:
        market_scores = sb.rank([s for s in all_scores if s.market == spec], by="brier")
        print(to_markdown(market_scores, sb.get_market(spec).name))

    # 4. where did the consensus beat the bookmaker? (per market)
    for spec in ["1x2", "ou_corners@9.5"]:
        bets = sb.find_value(fixtures, preds, market=spec, min_edge=0.08)
        print(f"\n{len(bets)} value bets on {spec} (edge>=8%). Top 3:")
        for b in bets[:3]:
            print(f"  {b.fixture:28s} {b.label:12s}  edge {b.edge:+.0%}  @ {b.decimal_odds}  kelly {b.kelly:.1%}")


if __name__ == "__main__":
    main()
