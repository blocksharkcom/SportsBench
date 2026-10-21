# Roadmap

SportsBench is young. Here's where it's going — contributions very welcome.

## Shipped (v0.2)
- **Configurable markets, any sport**: 1X2, double chance, draw‑no‑bet, BTTS,
  correct score, over/under (goals, corners, cards, tennis games/aces, basketball
  points), handicaps/spreads, match winner, moneyline — per‑sport config, multi‑market
  runs (`predict -m 1x2 -m ou_goals@2.5 …`), a leaderboard per market.
- **Per‑game snapshots** (`sportsbench game`): every model's call on one match.
- **One‑key setup** via OpenRouter (all models through a single key).
- **modelfights.com data source** (`--source modelfights`): free key for real
  fixtures/events/odds; Pro plan adds hosted runs + publish.

## Shipped (v0.1)
- Multi‑provider BYO‑key agents (OpenAI, Anthropic, Google, xAI, DeepSeek, OpenRouter, Groq, Mistral, Ollama/LM Studio, any OpenAI‑compatible endpoint)
- Same‑brief predictions with SHA‑256 pre‑kickoff proof
- Grading: win rate, Brier, log‑loss, ECE, ROI, units, closing‑line value
- Odds math: de‑vig (multiplicative/power), EV, fractional Kelly
- Consensus/ensemble + value‑bet finder with longshot guards
- SQLite persistence, CLI, markdown/json/csv + branded HTML export
- Offline demo dataset (`backtest --demo`), test suite

## Next
- [ ] The GUI: `sportsbench serve` local dashboard (then hosted on modelfights.com)
- [ ] modelfights.com API endpoints + key tiers (free data / paid data / pro compute)
- [ ] More data sources: API‑Football, OddsAPI, Pinnacle closing lines
- [ ] More sports wired end‑to‑end: tennis, basketball, NFL
- [ ] Budget guard: estimate + cap $ spend per run
- [ ] `sportsbench tournament` — head‑to‑head bracket between models
- [ ] GitHub Action template to auto‑run daily and publish a leaderboard

## Later
- [ ] Bankroll simulation + drawdown / Sharpe reporting
- [ ] Prompt‑variant A/B (does chain‑of‑thought change calibration?)
- [ ] Pluggable scoring rules
- [ ] Reproducibility bundle (hashes + raw responses) for published results

## How to contribute
A new provider is ~30 lines (see `src/sportsbench/providers/`). A new data source is two
methods (`src/sportsbench/sources/base.py`). Open an issue or PR.
