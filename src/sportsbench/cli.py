"""SportsBench command line.

  sportsbench init                     scaffold a config
  sportsbench models                   list configured models
  sportsbench backtest --demo          instant offline leaderboard (no keys)
  sportsbench predict --source demo    run your models on fixtures
  sportsbench fixtures --live          real upcoming events + odds (free modelfights.com key)
  sportsbench predict -s modelfights   predict on real events from modelfights.com
  sportsbench grade                    grade stored predictions vs results
  sportsbench leaderboard              show the standings
  sportsbench value                    find value bets vs the bookmaker
  sportsbench report --html out.html   export a branded leaderboard
  sportsbench publish                  [PRO] push leaderboard to modelfights.com
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .branding import show as show_banner
from .config import Config
from .engine import run_predictions
from .grading import score_predictions, rank, to_json, to_csv, to_markdown, to_html
from .providers import PROVIDERS
from .store import Store
from .value import find_value

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="The open benchmark for LLM sports prediction — modelfights.com")
console = Console()


def _cfg(path: Optional[str]) -> Config:
    return Config.load(path)


@app.command()
def version():
    """Print the version."""
    console.print(f"SportsBench {__version__}")


@app.command()
def serve(
    port: int = typer.Option(8787, "--port", "-p"),
    host: str = typer.Option("127.0.0.1", "--host"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open a browser."),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Launch the local dashboard — read data and run models in your browser."""
    from .webui import serve as _serve
    _serve(host=host, port=port, open_browser=not no_open, config=_cfg(config))


@app.command()
def init(path: str = "sportsbench.config.yaml"):
    """Write a starter config you can edit."""
    if Path(path).exists():
        console.print(f"[yellow]{path} already exists — not overwriting.[/yellow]")
        raise typer.Exit(1)
    Path(path).write_text(_STARTER_CONFIG)
    console.print(f"[green]Wrote {path}[/green] — add your API keys to a .env file and "
                  f"run [bold]sportsbench backtest --demo[/bold] to see it work.")


@app.command()
def models(config: Optional[str] = typer.Option(None, "--config", "-c")):
    """List configured models (and which providers are available)."""
    cfg = _cfg(config)
    if not cfg.models:
        console.print("[yellow]No config found.[/yellow] Run [bold]sportsbench init[/bold].")
        console.print(f"Supported providers: {', '.join(PROVIDERS)}")
        raise typer.Exit()
    t = Table("Model", "Provider", "Model ID", "Key set?", title="Configured models")
    for m in cfg.models:
        t.add_row(m.name, m.provider, m.model,
                  "[green]yes[/green]" if m.api_key() else "[red]no[/red]")
    console.print(t)
    show_banner(console, cfg.branding)


@app.command()
def markets(sport: str = typer.Option("football", "--sport", help="football|tennis|basketball")):
    """List the betting markets you can predict + grade for a sport."""
    from .markets import markets_for_sport, DEFAULT_MARKETS
    t = Table("Market spec", title=f"Markets available for {sport}")
    for m in markets_for_sport(sport):
        t.add_row(m)
    console.print(t)
    console.print(f"[dim]Enabled by default: {', '.join(DEFAULT_MARKETS.get(sport, ['1x2']))}[/dim]")
    console.print("[dim]Lines use @: ou_goals@2.5, ou_corners@9.5, ou_aces@20.5, spread@-1.5[/dim]")
    console.print("[dim]Run several at once:  sportsbench predict -m 1x2 -m ou_goals@2.5 -m btts[/dim]")


@app.command()
def backtest(
    demo: bool = typer.Option(False, "--demo", help="Use the bundled offline sample."),
    source: str = typer.Option("demo", "--source", "-s"),
    market: list[str] = typer.Option(None, "--market", "-m", help="Market(s); default = all in the data."),
    sort: str = typer.Option("brier", "--sort", help="brier|roi|win_rate|clv"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Grade a dataset end-to-end and print a leaderboard per market. --demo needs no keys."""
    from .sources import get_source
    cfg = _cfg(config)
    src = get_source("demo" if demo else source)
    fixtures = src.upcoming(limit=1000)
    results = src.results([f.id for f in fixtures])

    if demo:
        # the sample ships pre-made predictions (all markets) so it runs with zero keys
        from .sources.files import _read_json
        from importlib import resources
        from .types import Prediction
        with resources.as_file(resources.files("sportsbench.data")) as d:
            preds = [Prediction.from_dict(x) for x in _read_json(str(d / "demo_predictions.json"))]
    else:
        preds = run_predictions(cfg, fixtures, markets=_resolve_markets(cfg, market),
                                on_done=lambda p: _tick(p))

    scores = score_predictions(preds, results, cfg.stake_unit, fixtures={f.id: f for f in fixtures})
    _print_leaderboards(scores, sort, only=market)
    show_banner(console, cfg.branding)


@app.command()
def predict(
    source: str = typer.Option("demo", "--source", "-s",
                               help="demo | modelfights (free key) | football-data | json"),
    league: Optional[str] = typer.Option(None, "--league", "-l"),
    market: list[str] = typer.Option(None, "--market", "-m",
                                     help="Market(s) to run; repeatable. Default = config/defaults."),
    limit: int = typer.Option(20, "--limit", "-n"),
    fixtures_path: Optional[str] = typer.Option(None, "--fixtures"),
    db: str = typer.Option("sportsbench.db", "--db"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Run every configured model on upcoming fixtures, across one or more markets,
    and store locked predictions."""
    from .sources import get_source
    cfg = _cfg(config)
    if not cfg.active_models():
        console.print("[red]No models configured.[/red] Run [bold]sportsbench init[/bold].")
        raise typer.Exit(1)
    kwargs = {"fixtures_path": fixtures_path} if fixtures_path else {}
    src = get_source(source, **kwargs)
    fixtures = src.upcoming(league, limit)
    markets = _resolve_markets(cfg, market)
    console.print(f"Running [bold]{len(cfg.active_models())}[/bold] models on "
                  f"[bold]{len(fixtures)}[/bold] fixtures × [bold]{len(markets)}[/bold] "
                  f"markets [dim]({', '.join(markets)})[/dim]…")
    preds = run_predictions(cfg, fixtures, markets=markets, on_done=_tick)
    store = Store(db)
    store.save_fixtures(fixtures)
    store.save_predictions(preds)
    ok = sum(1 for p in preds if not p.error)
    console.print(f"\n[green]Stored {ok}/{len(preds)} predictions[/green] "
                  f"({len(preds)-ok} errors recorded) → {db}")
    show_banner(console, cfg.branding)


@app.command()
def game(
    fixture_id: Optional[str] = typer.Argument(None, help="Fixture id (from `fixtures --live`). Omit to pick one."),
    source: str = typer.Option("modelfights", "--source", "-s",
                               help="modelfights (free key) | demo | football-data"),
    league: Optional[str] = typer.Option(None, "--league", "-l"),
    market: list[str] = typer.Option(None, "--market", "-m", help="Market(s); default = config/defaults."),
    db: str = typer.Option("sportsbench.db", "--db"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Get every model's call on ONE specific game — a full prediction snapshot,
    across one or more markets.

    Shows the fixture, the odds, each model's pick + probabilities + reasoning, the
    consensus, and where the models beat the bookmaker's price.
    """
    from .sources import get_source
    from .pro import ModelFightsClient, NeedsKey, NeedsPro, ProError
    from .value import consensus, find_value
    from .markets import get_market
    cfg = _cfg(config)
    if not cfg.active_models():
        console.print("[red]No models configured.[/red] Run [bold]sportsbench init[/bold] and add keys.")
        raise typer.Exit(1)
    try:
        src = (get_source("modelfights", client=ModelFightsClient(cfg))
               if source in ("modelfights", "mf", "pro", "live") else get_source(source))
        fixtures = src.upcoming(league, 50)
    except (NeedsKey, NeedsPro, ProError) as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(2)
    if not fixtures:
        console.print("[yellow]No upcoming fixtures from this source.[/yellow]")
        raise typer.Exit(1)

    fx = next((f for f in fixtures if f.id == fixture_id), None) if fixture_id else None
    if fx is None:
        if fixture_id:
            console.print(f"[yellow]Fixture {fixture_id} not found in upcoming list.[/yellow]")
        tbl = Table("#", "Fixture", "League", "Kickoff", title="Upcoming games")
        for i, f in enumerate(fixtures[:25], 1):
            tbl.add_row(str(i), f.label(), f.league, f.kickoff)
        console.print(tbl)
        choice = typer.prompt("Pick a game number", type=int)
        if not (1 <= choice <= min(25, len(fixtures))):
            raise typer.Exit(1)
        fx = fixtures[choice - 1]

    specs = _resolve_markets(cfg, market, fx.sport)
    console.print(f"\n[bold]{fx.label()}[/bold]  [dim]· {fx.league} · {fx.kickoff}[/dim]")
    console.print(f"  Running {len(cfg.active_models())} models × {len(specs)} markets…\n")

    preds = run_predictions(cfg, [fx], markets=specs, on_done=_tick)
    Store(db).save_fixtures([fx])
    Store(db).save_predictions(preds)

    for spec in specs:
        mk = get_market(spec)
        keys = mk.selection_keys()
        mpreds = [p for p in preds if (p.market or "1x2") == spec]
        odds = fx.market_odds(spec) or {}
        head = f"Snapshot · {mk.name}"
        if odds:
            head += "   odds " + " ".join(f"{mk.label_for(k)}:{v}" for k, v in odds.items())
        # compact, works for any market (even 17-way correct score): pick + P(pick)
        t = Table("Model", "Pick", "P(pick)", "Conf", "Why", title=head)
        for p in sorted(mpreds, key=lambda x: (x.error is not None, -x.confidence)):
            if p.error:
                t.add_row(p.model, "[red]error[/red]", "—", "—", p.error[:44])
                continue
            t.add_row(p.model, f"[green]{mk.label_for(p.pick)}[/green]",
                      f"{p.probs.get(p.pick,0):.0%}", f"{p.confidence:.0%}", (p.rationale or "")[:42])
        cons = consensus([p for p in mpreds if not p.error], keys)
        if any(cons.values()):
            cpick = max(cons, key=cons.get)
            t.add_section()
            t.add_row("[bold]CONSENSUS[/bold]", f"[bold]{mk.label_for(cpick)}[/bold]",
                      f"[bold]{cons[cpick]:.0%}[/bold]", "", "")
        console.print(t)
        bets = find_value([fx], preds, market=spec, min_edge=0.02,
                          kelly_fraction=cfg.kelly_fraction, devig_method=cfg.devig, source="consensus")
        for b in bets:
            console.print(f"  [green]value[/green] {b.label}: consensus {b.model_prob:.0%} vs "
                          f"fair {b.fair_prob:.0%} @ {b.decimal_odds:g}  edge {b.edge:+.0%}  kelly {b.kelly:.1%}")
        console.print()

    console.print("[dim]Informational only — not betting advice.[/dim]")
    show_banner(console, cfg.branding)


@app.command()
def grade(
    source: str = typer.Option("demo", "--source", "-s"),
    db: str = typer.Option("sportsbench.db", "--db"),
    market: list[str] = typer.Option(None, "--market", "-m", help="Filter to market(s)."),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Fetch results for stored predictions and print a leaderboard per market."""
    from .sources import get_source
    cfg = _cfg(config)
    store = Store(db)
    preds = store.predictions()
    if not preds:
        console.print("[yellow]No stored predictions. Run `sportsbench predict` first.[/yellow]")
        raise typer.Exit(1)
    fids = sorted({p.fixture_id for p in preds})
    results = get_source(source).results(fids)
    store.save_results(results)
    fxmap = {f.id: f for f in store.fixtures()}
    scores = score_predictions(preds, results, cfg.stake_unit, fixtures=fxmap)
    _print_leaderboards(scores, sort, only=market)
    show_banner(console, cfg.branding)


@app.command()
def leaderboard(
    db: str = typer.Option("sportsbench.db", "--db"),
    market: list[str] = typer.Option(None, "--market", "-m", help="Filter to market(s)."),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Show standings (per market) from already-graded predictions."""
    cfg = _cfg(config)
    store = Store(db)
    fxmap = {f.id: f for f in store.fixtures()}
    scores = score_predictions(store.predictions(), store.results(),
                               cfg.stake_unit, fixtures=fxmap)
    _print_leaderboards(scores, sort, only=market)
    show_banner(console, cfg.branding)


@app.command()
def value(
    db: str = typer.Option("sportsbench.db", "--db"),
    market: list[str] = typer.Option(None, "--market", "-m", help="Market(s); default = all in the data."),
    min_edge: float = typer.Option(0.03, "--min-edge", help="Minimum EV per unit."),
    source: str = typer.Option("consensus", "--from", help="'consensus' or a model name."),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Find value bets across markets: where the models beat the bookmaker's price."""
    cfg = _cfg(config)
    store = Store(db)
    fixtures, preds = store.fixtures(), store.predictions()
    specs = market or sorted({p.market or "1x2" for p in preds})
    bets = []
    for spec in specs:
        bets += find_value(fixtures, preds, market=spec, min_edge=min_edge,
                           kelly_fraction=cfg.kelly_fraction, devig_method=cfg.devig, source=source)
    bets.sort(key=lambda b: b.edge, reverse=True)
    if not bets:
        console.print("[yellow]No value found at this threshold.[/yellow]")
        raise typer.Exit()
    t = Table("Fixture", "Market", "Pick", "From", "Model%", "Fair%", "Odds", "Edge", "Kelly",
              title=f"Value bets (min edge {min_edge:+.0%})")
    for b in bets:
        t.add_row(b.fixture, b.market, b.label, b.source, f"{b.model_prob:.0%}", f"{b.fair_prob:.0%}",
                  f"{b.decimal_odds:g}", f"[green]{b.edge:+.1%}[/green]", f"{b.kelly:.1%}")
    console.print(t)
    console.print("[dim]Informational only — not betting advice. Stake responsibly.[/dim]")
    show_banner(console, cfg.branding)


@app.command()
def report(
    db: str = typer.Option("sportsbench.db", "--db"),
    html: Optional[str] = typer.Option(None, "--html", help="Write branded HTML here."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown|json|csv"),
    market: Optional[str] = typer.Option(None, "--market", "-m", help="Which market (default 1x2)."),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Export one market's leaderboard (markdown/json/csv, or a branded HTML page)."""
    cfg = _cfg(config)
    store = Store(db)
    fxmap = {f.id: f for f in store.fixtures()}
    allscores = score_predictions(store.predictions(), store.results(), cfg.stake_unit, fixtures=fxmap)
    specs = []
    for s in allscores:
        if s.market not in specs:
            specs.append(s.market)
    spec = market or ("1x2" if "1x2" in specs else (specs[0] if specs else "1x2"))
    scores = rank([s for s in allscores if s.market == spec], by=sort)
    title = f"SportsBench — {_market_name(spec)}"
    if html:
        Path(html).write_text(to_html(scores, title))
        console.print(f"[green]Wrote {html}[/green] ({_market_name(spec)} — branded, links to modelfights.com)")
        return
    out = {"markdown": lambda s: to_markdown(s, title), "json": to_json, "csv": to_csv}[fmt](scores)
    console.print(out)


@app.command()
def fixtures(
    live: bool = typer.Option(False, "--live",
                              help="Fetch real upcoming events from modelfights.com (free key)."),
    league: Optional[str] = typer.Option(None, "--league", "-l"),
    limit: int = typer.Option(20, "--limit", "-n"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """List fixtures. --live pulls real upcoming events + odds from modelfights.com
    (free — just sign up for a key). Without --live, shows the offline demo set."""
    from .pro import ModelFightsClient, NeedsKey, NeedsPro, ProError
    from .sources import get_source
    cfg = _cfg(config)
    try:
        src = get_source("modelfights", client=ModelFightsClient(cfg)) if live else get_source("demo")
        fx = src.upcoming(league, limit)
    except (NeedsKey, NeedsPro, ProError) as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(2)
    t = Table("ID", "League", "Fixture", "Kickoff", "Odds", title="Fixtures")
    for f in fx:
        odds = f.odds.to_dict() if f.odds else {}
        t.add_row(f.id, f.league, f.label(), f.kickoff,
                  " ".join(f"{k}:{v}" for k, v in odds.items()))
    console.print(t)
    show_banner(console, cfg.branding)


@app.command()
def publish(
    db: str = typer.Option("sportsbench.db", "--db"),
    title: str = typer.Option("My SportsBench run", "--title"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """[PRO] Publish your leaderboard to a shareable public page on modelfights.com."""
    from .pro import ModelFightsClient, NeedsKey, NeedsPro, ProError
    cfg = _cfg(config)
    store = Store(db)
    scores = rank(score_predictions(store.predictions(), store.results(), cfg.stake_unit))
    try:
        url = ModelFightsClient(cfg).publish({"rows": [s.to_row() for s in scores]}, title)
    except (NeedsKey, NeedsPro, ProError) as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(2)
    console.print(f"[green]Published:[/green] {url}")


# ---- helpers ----
def _tick(p):
    mark = "[red]✗[/red]" if p.error else "[green]✓[/green]"
    console.print(f"  {mark} {p.model:<22} {('ERROR: ' + p.error) if p.error else p.pick}")


def _resolve_markets(cfg, market_opt, sport=None):
    """Market specs from --market (repeatable) or the config's per-sport defaults."""
    if market_opt:
        return list(market_opt)
    return cfg.market_specs(sport or cfg.sport)


def _market_name(spec: str) -> str:
    try:
        from .markets import get_market
        m = get_market(spec)
        return f"{m.name} ({spec})" if m.line is not None else m.name
    except Exception:
        return spec


def _print_leaderboards(scores, sort: str, only=None):
    """Print one leaderboard table per market present in the scores."""
    specs = []
    for s in scores:
        if s.market not in specs:
            specs.append(s.market)
    if only:
        wanted = set(only)
        specs = [s for s in specs if s in wanted] or list(wanted)
    if not specs:
        console.print("[yellow]Nothing to grade yet.[/yellow]")
        return
    for spec in specs:
        sub = rank([s for s in scores if s.market == spec], by=sort)
        if sub:
            _print_leaderboard(sub, f"{_market_name(spec)} · sorted by {sort}")


def _print_leaderboard(scores, title: str):
    t = Table("#", "Model", "Picks", "Win%", "Brier", "ROI%", "Units", "CLV%", "ECE",
              "Err", title=title)
    for i, s in enumerate(scores, 1):
        r = s.to_row()
        t.add_row(str(i), r["model"], str(r["settled"]), _s(r["win_rate"], "%"),
                  _s(r["brier"]), _s(r["roi"], "%"), _s(r["units"]), _s(r["clv"], "%"),
                  _s(r["ece"]), str(r["errors"]))
    console.print(t)


def _s(v, suffix="") -> str:
    return "—" if v is None else f"{v}{suffix}"


_STARTER_CONFIG = """# SportsBench — https://modelfights.com
#
# EASIEST SETUP: one OpenRouter key runs every model.
#   1. Get a key at https://openrouter.ai/keys
#   2. Put it in a .env file next to this config:  OPENROUTER_API_KEY=sk-or-...
#   3. sportsbench predict --source demo   (or --source modelfights for real games)
#
defaults:
  sport: football
  devig: multiplicative   # or: power
  stake_unit: 1.0
  kelly_fraction: 0.25
branding: true

# Markets predicted + graded by default, per sport. See: sportsbench markets --sport football
markets:
  football:   [1x2, ou_goals@2.5, btts, correct_score, ou_corners@9.5]
  tennis:     [match_winner, ou_games@22.5, ou_aces@20.5]
  basketball: [moneyline, ou_points@210.5, spread@-5.5]

# One key, every model (recommended) — all routed through OpenRouter:
models:
  - { name: GPT-5,           provider: openrouter, model: openai/gpt-5,                 api_key_env: OPENROUTER_API_KEY }
  - { name: Claude Opus 4.8, provider: openrouter, model: anthropic/claude-opus-4,      api_key_env: OPENROUTER_API_KEY }
  - { name: Gemini 3 Pro,    provider: openrouter, model: google/gemini-3-pro,          api_key_env: OPENROUTER_API_KEY }
  - { name: Grok 4,          provider: openrouter, model: x-ai/grok-4,                   api_key_env: OPENROUTER_API_KEY }
  - { name: DeepSeek V3,     provider: openrouter, model: deepseek/deepseek-chat,        api_key_env: OPENROUTER_API_KEY }
  - { name: Llama 3 (local), provider: ollama,     model: llama3 }   # free, local, no key

# Prefer your OWN per-provider keys? Swap the lines above for these and set each *_API_KEY:
#  - { name: GPT-5,           provider: openai,    model: gpt-5,           api_key_env: OPENAI_API_KEY }
#  - { name: Claude Opus 4.8, provider: anthropic, model: claude-opus-4-8, api_key_env: ANTHROPIC_API_KEY }
#  - { name: Gemini 3 Pro,    provider: google,    model: gemini-3-pro,    api_key_env: GEMINI_API_KEY }
#  - { name: Grok 4,          provider: grok,      model: grok-4,          api_key_env: XAI_API_KEY }
#  - { name: DeepSeek V3,     provider: deepseek,  model: deepseek-chat,   api_key_env: DEEPSEEK_API_KEY }

# modelfights.com — the easiest way to get real data.
#   FREE key (just sign up): fetch upcoming fixtures, events + odds across 45+ leagues
#     ->  sportsbench predict --source modelfights --league epl
#   PRO plan (same key): hosted model runs (no LLM keys needed) + cloud publish
# Get your free key at https://modelfights.com/sportsbench
modelfights:
  api_key_env: MODELFIGHTS_API_KEY
  base_url: https://modelfights.com/v1
"""


def main():
    app()


if __name__ == "__main__":
    main()
