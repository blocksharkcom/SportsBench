<div align="center">

# 🏟️ SportsBench

### The open benchmark for LLM sports prediction

**Can GPT‑5, Claude, Gemini and Grok actually beat the bookmakers?**
Give every model the *same* brief, lock each pick before kickoff, and grade them in public — win rate, calibration, ROI and closing‑line value. Bring your own API keys; run it on your laptop in 10 seconds.

[![PyPI](https://img.shields.io/pypi/v/sportsbench.svg)](https://pypi.org/project/sportsbench/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Live leaderboard](https://img.shields.io/badge/live-modelfights.com-22c55e.svg)](https://modelfights.com)

*A live, continuously‑graded version runs at **[modelfights.com](https://modelfights.com)** — 45+ frontier models, updated daily.*

</div>

---

## Why

Every AI company claims their model "reasons." Sports is the ultimate honest test: a probabilistic question with a public, unarguable answer a few hours later, and a brutally efficient market (the closing line) to beat. SportsBench turns that into a reproducible benchmark — and a tool a bettor can actually use.

- **Same brief, every model.** Fair by construction. No model gets extra hints.
- **Locked before kickoff.** Each prompt is SHA‑256 hashed, so predictions can't be edited with hindsight.
- **Graded on what matters.** Not just win rate (which flatters favourite‑backers) but **calibration** (Brier, log‑loss, ECE) and **money** (ROI, units, closing‑line value).
- **Bring your own keys.** OpenAI, Anthropic, Google, xAI, DeepSeek, OpenRouter, Groq, Mistral… or **Ollama / LM Studio locally for $0**. You pay your providers; SportsBench is free.

## 10‑second demo (no API keys)

```bash
pip install sportsbench
sportsbench backtest --demo
```

```
                         Backtest · sorted by brier
 #  Model             Picks  Win%   Brier   ROI%    Units   CLV%    ECE     Err
 1  GPT-5             300    49.3%  0.6355  -18.8%  -56.29  -0.16%  0.131   0
 2  Claude Opus 4.8   300    49.3%  0.6360  -18.6%  -55.80  -0.17%  0.078   0
 3  Gemini 3 Pro      300    48.7%  0.6397  -20.4%  -61.29  -0.13%  0.134   0
 4  Grok 4            300    48.0%  0.6407  -22.1%  -66.26  -0.13%  0.241   0
 5  Llama 3 (local)   293    48.8%  0.6459  -20.5%  -60.08  -0.12%  0.184   7
 6  DeepSeek V3       295    48.1%  0.6466  -22.4%  -66.09  -0.12%  0.277   5
```

> The sample is synthetic, but the lesson is real and the same one the live site shows:
> **win rate barely separates the models — calibration does.** And flat‑betting every pick
> bleeds the bookmaker's margin, which is why the value finder (below) matters.

## Run it for real

```bash
sportsbench init                     # writes sportsbench.config.yaml
# put your keys in a .env file (OPENAI_API_KEY=..., ANTHROPIC_API_KEY=..., etc.)

sportsbench predict --source demo    # every model predicts, picks are locked
sportsbench grade                    # fetch results, print the leaderboard
sportsbench value --min-edge 0.05    # where the models beat the bookmaker's price
sportsbench report --html out.html   # a shareable, branded leaderboard page
```

Point it at real fixtures with the free [football-data.org](https://www.football-data.org) tier, your own CSV/JSON, or the Pro live feed:

```bash
export FOOTBALL_DATA_API_KEY=...      # free key
sportsbench predict --source football-data --league epl
```

## Value bets — the bettor's view

```
Value bets (min edge +5%)
 Fixture                 Pick   From       Model%  Fair%  Odds   Edge    Kelly
 Wolves vs Everton       draw   consensus  16%     13%    7.48   +22%    2.8%
 Wolves vs Sheffield Utd home   consensus  22%     18%    5.32   +18%    4.1%
 Arsenal vs Nott'm Forest draw  consensus  15%     12%    7.94   +17%    2.5%
```

De‑vig (multiplicative or power), expected value, and fractional‑Kelly staking are built in. Guards against the longshot trap are on by default. *Informational only — not betting advice.*

## Supported providers (bring your own key)

| Provider | `provider:` | Notes |
|---|---|---|
| OpenAI | `openai` | GPT‑5, o‑series |
| Anthropic | `anthropic` | Claude |
| Google | `google` | Gemini |
| xAI | `grok` | Grok |
| DeepSeek | `deepseek` | |
| OpenRouter / Together / Groq / Mistral / Fireworks | `openrouter` … | any OpenAI‑compatible gateway |
| **Ollama / LM Studio** | `ollama` / `lmstudio` | **local, free, no key** |
| *anything else* | `openai_compatible` | set your own `base_url` |

## What the metrics mean

| Metric | Reads | Why it matters |
|---|---|---|
| **Win%** | higher | intuitive, but flatters anyone who just backs favourites |
| **Brier** | lower | squared error of the probabilities — the core skill score |
| **Log‑loss** | lower | punishes confident wrong calls harder |
| **ECE** | lower | expected calibration error — does "70%" really mean 70%? |
| **ROI / Units** | higher | profit to flat stakes at the odds when the pick was made |
| **CLV** | higher | closing‑line value — did you beat the price the market closed at? The sharpest long‑run signal. |

## Use it as a library

```python
import sportsbench as sb

cfg = sb.Config.load()                       # reads sportsbench.config.yaml
fixtures = sb.sources.DemoSource().upcoming()
preds = sb.run_predictions(cfg, fixtures)    # every model, same locked brief
scores = sb.rank(sb.score_predictions(preds, results))
bets = sb.find_value(fixtures, preds, min_edge=0.05)
```

## SportsBench Pro & the hosted version

The package is free and fully functional with your own keys. **Pro** (via [modelfights.com](https://modelfights.com/sportsbench)) removes all the setup:

- **Managed live fixtures + real odds** across 45+ leagues — no third‑party keys.
- **Hosted model runs** — we execute the models server‑side, so you don't need any LLM keys.
- **Cloud publish** — push your leaderboard to a shareable public page.
- **Continuous auto‑grading, history, and alerts** on the web.

```bash
export SPORTSBENCH_API_KEY=...        # from modelfights.com/sportsbench
sportsbench fixtures --live --league epl
sportsbench publish --title "My EPL run"
```

## Roadmap

See [ROADMAP.md](ROADMAP.md). PRs welcome — new providers and data sources are the easiest first contribution.

## Disclaimer

SportsBench is a research and benchmarking tool. Outputs are informational, not betting advice. Gamble responsibly and only where legal in your jurisdiction.

## License

MIT — see [LICENSE](LICENSE). Built by the team behind **[modelfights.com](https://modelfights.com)**, where you can watch 45+ frontier models get graded on real matches, in public, every day.
