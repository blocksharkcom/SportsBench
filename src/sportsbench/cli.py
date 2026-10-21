"""SportsBench command line.

  sportsbench init                     scaffold a config
  sportsbench models                   list configured models
  sportsbench backtest --demo          instant offline leaderboard (no keys)
  sportsbench predict --source demo    run your models on fixtures
  sportsbench grade                    grade stored predictions vs results
  sportsbench leaderboard              show the standings
  sportsbench value                    find value bets vs the bookmaker
  sportsbench report --html out.html   export a branded leaderboard
  sportsbench fixtures --live          [PRO] managed live fixtures + odds
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
def backtest(
    demo: bool = typer.Option(False, "--demo", help="Use the bundled offline sample."),
    source: str = typer.Option("demo", "--source", "-s"),
    sort: str = typer.Option("brier", "--sort", help="brier|roi|win_rate|clv"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Grade a dataset end-to-end and print the leaderboard. --demo needs no keys."""
    from .sources import get_source
    cfg = _cfg(config)
    src = get_source("demo" if demo else source)
    fixtures = src.upcoming(limit=500)
    results = src.results([f.id for f in fixtures])

    if demo:
        # the sample ships pre-made predictions so it runs with zero keys
        from .sources.files import _read_json
        from importlib import resources
        from .types import Prediction
        with resources.as_file(resources.files("sportsbench.data")) as d:
            preds = [Prediction.from_dict(x) for x in _read_json(str(d / "demo_predictions.json"))]
    else:
        preds = run_predictions(cfg, fixtures, on_done=lambda p: _tick(p))

    scores = rank(score_predictions(preds, results, cfg.stake_unit,
                                     fixtures={f.id: f for f in fixtures}), by=sort)
    _print_leaderboard(scores, f"Backtest · sorted by {sort}")
    show_banner(console, cfg.branding)


@app.command()
def predict(
    source: str = typer.Option("demo", "--source", "-s", help="demo|json|football-data|pro"),
    league: Optional[str] = typer.Option(None, "--league", "-l"),
    limit: int = typer.Option(20, "--limit", "-n"),
    fixtures_path: Optional[str] = typer.Option(None, "--fixtures"),
    db: str = typer.Option("sportsbench.db", "--db"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Run every configured model on upcoming fixtures and store locked predictions."""
    from .sources import get_source
    cfg = _cfg(config)
    if not cfg.active_models():
        console.print("[red]No models configured.[/red] Run [bold]sportsbench init[/bold].")
        raise typer.Exit(1)
    kwargs = {"fixtures_path": fixtures_path} if fixtures_path else {}
    src = get_source(source, **kwargs)
    fixtures = src.upcoming(league, limit)
    console.print(f"Running [bold]{len(cfg.active_models())}[/bold] models on "
                  f"[bold]{len(fixtures)}[/bold] fixtures…")
    preds = run_predictions(cfg, fixtures, on_done=_tick)
    store = Store(db)
    store.save_fixtures(fixtures)
    store.save_predictions(preds)
    ok = sum(1 for p in preds if not p.error)
    console.print(f"\n[green]Stored {ok}/{len(preds)} predictions[/green] "
                  f"({len(preds)-ok} errors recorded) → {db}")
    show_banner(console, cfg.branding)


@app.command()
def grade(
    source: str = typer.Option("demo", "--source", "-s"),
    db: str = typer.Option("sportsbench.db", "--db"),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Fetch results for stored predictions and print the leaderboard."""
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
    scores = rank(score_predictions(preds, results, cfg.stake_unit, fixtures=fxmap), by=sort)
    _print_leaderboard(scores, f"Leaderboard · sorted by {sort}")
    show_banner(console, cfg.branding)


@app.command()
def leaderboard(
    db: str = typer.Option("sportsbench.db", "--db"),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Show standings from already-graded predictions."""
    cfg = _cfg(config)
    store = Store(db)
    fxmap = {f.id: f for f in store.fixtures()}
    scores = rank(score_predictions(store.predictions(), store.results(),
                                    cfg.stake_unit, fixtures=fxmap), by=sort)
    _print_leaderboard(scores, f"Leaderboard · sorted by {sort}")
    show_banner(console, cfg.branding)


@app.command()
def value(
    db: str = typer.Option("sportsbench.db", "--db"),
    min_edge: float = typer.Option(0.03, "--min-edge", help="Minimum EV per unit."),
    source: str = typer.Option("consensus", "--from", help="'consensus' or a model name."),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Find value bets: where the models beat the bookmaker's price."""
    cfg = _cfg(config)
    store = Store(db)
    bets = find_value(store.fixtures(), store.predictions(),
                      min_edge=min_edge, kelly_fraction=cfg.kelly_fraction,
                      devig_method=cfg.devig, source=source)
    if not bets:
        console.print("[yellow]No value found at this threshold.[/yellow]")
        raise typer.Exit()
    t = Table("Fixture", "Pick", "From", "Model%", "Fair%", "Odds", "Edge", "Kelly",
              title=f"Value bets (min edge {min_edge:+.0%})")
    for b in bets:
        t.add_row(b.fixture, b.pick, b.source, f"{b.model_prob:.0%}", f"{b.fair_prob:.0%}",
                  f"{b.decimal_odds:g}", f"[green]{b.edge:+.1%}[/green]", f"{b.kelly:.1%}")
    console.print(t)
    console.print("[dim]Informational only — not betting advice. Stake responsibly.[/dim]")
    show_banner(console, cfg.branding)


@app.command()
def report(
    db: str = typer.Option("sportsbench.db", "--db"),
    html: Optional[str] = typer.Option(None, "--html", help="Write branded HTML here."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown|json|csv"),
    sort: str = typer.Option("roi", "--sort"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """Export the leaderboard (markdown/json/csv, or a shareable branded HTML page)."""
    cfg = _cfg(config)
    store = Store(db)
    fxmap = {f.id: f for f in store.fixtures()}
    scores = rank(score_predictions(store.predictions(), store.results(),
                                    cfg.stake_unit, fixtures=fxmap), by=sort)
    if html:
        Path(html).write_text(to_html(scores))
        console.print(f"[green]Wrote {html}[/green] (branded — links to modelfights.com)")
        return
    out = {"markdown": to_markdown, "json": lambda s: to_json(s), "csv": to_csv}[fmt](scores)
    console.print(out)


@app.command()
def fixtures(
    live: bool = typer.Option(False, "--live", help="[PRO] managed fixtures + odds."),
    league: Optional[str] = typer.Option(None, "--league", "-l"),
    limit: int = typer.Option(20, "--limit", "-n"),
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """List fixtures. --live uses the Pro managed feed (no third-party keys)."""
    from .pro import ProClient, NeedsPro, ProError
    from .sources import get_source
    cfg = _cfg(config)
    try:
        src = get_source("pro", client=ProClient(cfg)) if live else get_source("demo")
        fx = src.upcoming(league, limit)
    except (NeedsPro, ProError) as e:
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
    from .pro import ProClient, NeedsPro, ProError
    cfg = _cfg(config)
    store = Store(db)
    scores = rank(score_predictions(store.predictions(), store.results(), cfg.stake_unit))
    try:
        url = ProClient(cfg).publish({"rows": [s.to_row() for s in scores]}, title)
    except (NeedsPro, ProError) as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(2)
    console.print(f"[green]Published:[/green] {url}")


# ---- helpers ----
def _tick(p):
    mark = "[red]✗[/red]" if p.error else "[green]✓[/green]"
    console.print(f"  {mark} {p.model:<22} {('ERROR: ' + p.error) if p.error else p.pick}")


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
# Bring your own API keys (put them in a .env file next to this config).
defaults:
  sport: football
  devig: multiplicative   # or: power
  stake_unit: 1.0
  kelly_fraction: 0.25
branding: true

models:
  - name: GPT-5
    provider: openai
    model: gpt-5
    api_key_env: OPENAI_API_KEY
  - name: Claude Opus 4.8
    provider: anthropic
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY
  - name: Gemini 3 Pro
    provider: google
    model: gemini-3-pro
    api_key_env: GEMINI_API_KEY
  - name: Grok 4
    provider: grok              # preset base_url for x.ai
    model: grok-4
    api_key_env: XAI_API_KEY
  - name: DeepSeek V3
    provider: deepseek
    model: deepseek-chat
    api_key_env: DEEPSEEK_API_KEY
  - name: Llama 3 (local, free)
    provider: ollama            # http://localhost:11434/v1
    model: llama3
    # no key needed for local Ollama

# Optional paid layer — unlocks live data, hosted runs, cloud publish.
# Get a key at https://modelfights.com/sportsbench
pro:
  api_key_env: SPORTSBENCH_API_KEY
  base_url: https://modelfights.com/v1
"""


def main():
    app()


if __name__ == "__main__":
    main()
