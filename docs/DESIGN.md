# SportsBench — Design

How the pieces fit, and the data model that makes "any model, any game, any market,
any sport" work. This is the contract the CLI, the API and the GUI all build on.

## The system

```
            ┌──────────────────────────── modelfights.com API ───────────────────────────┐
            │  /v1/sportsbench  ·  data (fixtures, events, odds, results, snapshots)       │
            │                      compute (hosted model runs)  ·  publish                 │
            │  keys + metering + billing (free / data / pro tiers)                         │
            └───────────────▲───────────────────────────────▲──────────────────────────────┘
                            │ MODELFIGHTS_API_KEY            │
   ┌────────────────────────┴───────┐             ┌──────────┴───────────┐
   │  SportsBench (open-source SDK)  │             │  Hosted GUI = site    │
   │  core · providers · markets ·   │             │  (paid, zero setup)   │
   │  grading · value · CLI · serve  │             └───────────────────────┘
   └───────────────▲─────────────────┘
                   │ pip install
        ┌──────────┴──────────┐
        │  Local GUI dashboard │  (`sportsbench serve`, BYO keys, free)
        └──────────────────────┘
```

Same core, three faces. The API is the product; the SDK makes it easy; the GUI makes
it usable by bettors who'll never touch a terminal.

## The core object: a **Market**

Everything generalises from one idea — a *market* is a named set of **selections**
with odds, that a model assigns probabilities to and that a result **settles**.

```python
Selection(key="over", label="Over 2.5")

Market(
  key="ou_goals",            # stable id
  name="Total goals O/U",
  sports=["football"],       # or ["*"]
  kind="categorical",        # categorical (probs sum to 1) | lines (one O/U per line)
  line=2.5,                  # for O/U, handicap, totals
  stat="goals",              # which result stat settles it
  selections=[Selection("over","Over 2.5"), Selection("under","Under 2.5")],
  settle=lambda r: "over" if r.total("goals") > 2.5 else "under",
)
```

A **fixture** carries odds *per market*:

```python
fixture.markets = {
  "1x2":        {"home": 1.95, "draw": 3.7, "away": 4.1},
  "ou_goals@2.5": {"over": 1.9, "under": 1.95},
  "btts":       {"yes": 1.8, "no": 2.0},
  "correct_score": {"1-0": 7.5, "2-1": 8.0, ...},
}
```

A **result** carries the stats needed to settle any market (not just the score):

```python
Result(fixture_id, stats={
  "home": {"goals": 2, "corners": 6, "cards": 1, "aces": 0},
  "away": {"goals": 1, "corners": 4, "cards": 2, "aces": 0},
})
# r.total("corners") == 10 ; r.score() == (2, 1)
```

Then **everything downstream is market-agnostic**:
- **Brief** builds the JSON schema from the market's selections (so the model answers
  exactly the right shape — 1X2, O/U, correct score, aces…).
- **Engine** stores a prediction per (model, fixture, market).
- **Grading** calls `market.settle(result)` → metrics (Brier/ROI/CLV) per market.
- **Value** compares model probs to that market's odds.

## Built-in market catalog (configurable, extensible)

Users enable markets per sport in `sportsbench.config.yaml`:

```yaml
markets:
  football: [1x2, double_chance, btts, ou_goals@2.5, ou_goals@3.5, correct_score,
             ou_corners@9.5, ou_cards@3.5, ht_result, dnb, ah@-1]
  tennis:   [match_winner, set_betting, ou_games@22.5, ou_aces@20.5, tiebreak]
  basketball: [moneyline, spread@-5.5, ou_points@210.5]
```

Ship a solid catalog; adding one is a dataclass + a `settle` lambda (documented).
`sportsbench markets --sport football` lists what's available. Odds for a market are
provided by the data source (modelfights.com serves them per market); markets with no
odds are still predicted and graded (just no ROI/CLV).

## Snapshots

A **snapshot** is the immutable record for one (game, market) at a point in time:
the odds, every model's probabilities + pick + rationale, the consensus, the value,
and the prompt hash. Works for upcoming *and* past games. Snapshots are the unit the
GUI browses and the API sells (historical snapshots = a data tier).

## Monetisation (one key, three lines)
Data API (fetch fixtures/events/odds/results/**historical snapshots**) · Compute
(hosted runs) · Hosted GUI subscription. Free tier for adoption; metered paid tiers.
See the live site for pricing.

## Build order
1. **Markets core** in the SDK (this doc's data model) — foundational; API + GUI depend on it.
2. **modelfights.com API** endpoints + keys/metering/pricing.
3. **Local GUI** (`sportsbench serve`) → then hosted GUI polish.
```
