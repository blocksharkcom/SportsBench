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

    # 3. grade + rank
    scores = sb.rank(sb.score_predictions(preds, results, fixtures=fixtures_by_id), by="brier")
    print(to_markdown(scores, "Demo leaderboard"))

    # 4. where did the consensus beat the bookmaker?
    bets = sb.find_value(fixtures, preds, min_edge=0.08)
    print(f"\n{len(bets)} value bets found. Top 5:")
    for b in bets[:5]:
        print(f"  {b.fixture:28s} {b.pick:5s}  edge {b.edge:+.0%}  @ {b.decimal_odds}  kelly {b.kelly:.1%}")


if __name__ == "__main__":
    main()
