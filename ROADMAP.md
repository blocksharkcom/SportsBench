# Roadmap

SportsBench is young. Here's where it's going — contributions very welcome.

## Shipped (v0.1)
- Multi‑provider BYO‑key agents (OpenAI, Anthropic, Google, xAI, DeepSeek, OpenRouter, Groq, Mistral, Ollama/LM Studio, any OpenAI‑compatible endpoint)
- Same‑brief predictions with SHA‑256 pre‑kickoff proof
- Grading: win rate, Brier, log‑loss, ECE, ROI, units, closing‑line value
- Odds math: de‑vig (multiplicative/power), EV, fractional Kelly
- Consensus/ensemble + value‑bet finder with longshot guards
- SQLite persistence, CLI, markdown/json/csv + branded HTML export
- Offline demo dataset (`backtest --demo`), test suite

## Next (v0.2)
- [ ] More sports out of the box: tennis, basketball, NFL (2‑way markets already modelled)
- [ ] More data sources: API‑Football, OddsAPI, Pinnacle closing lines
- [ ] Per‑league / per‑market leaderboard breakdowns
- [ ] Calibration curve plot export (SVG)
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
