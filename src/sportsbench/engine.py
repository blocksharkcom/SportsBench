"""The engine: give every model the same locked brief, for every market, collect
predictions. One run can span many models × many fixtures × many markets.

Errors are recorded on the prediction (never hidden) — a model that fails or runs
out of credit shows up as an error row, exactly like the public record on the site.
"""
from __future__ import annotations

import concurrent.futures as cf
from typing import Callable, Optional

from .brief import SYSTEM, build_user_prompt, normalise_probs
from .config import Config, ModelConfig
from .markets import Market, get_market
from .proof import prompt_hash
from .providers import build_provider, extract_json, ProviderError
from .types import Fixture, Prediction


def predict_one(mc: ModelConfig, fixture: Fixture, market: Market) -> Prediction:
    user = build_user_prompt(fixture, market)
    phash = prompt_hash(SYSTEM, user)
    keys = market.selection_keys()
    base = dict(
        fixture_id=fixture.id, model=mc.name, provider=mc.provider, market=market.spec,
        odds_at_pick=fixture.market_odds(market.spec), prompt_sha256=phash,
    )
    try:
        provider = build_provider(mc)
        raw = provider.complete(SYSTEM, user)
        data = extract_json(raw)
        probs = normalise_probs(data.get("probs", {}), keys)
        pick = data.get("pick")
        if pick not in keys:
            pick = max(probs, key=probs.get)
        conf = float(data.get("confidence", probs.get(pick, 0.0)))
        return Prediction(
            pick=pick, probs=probs, confidence=max(0.0, min(1.0, conf)),
            rationale=str(data.get("rationale", ""))[:400], **base,
        )
    except Exception as e:  # recorded, not fatal
        return Prediction(
            pick="", probs={k: 0.0 for k in keys}, confidence=0.0,
            rationale="", error=f"{type(e).__name__}: {e}", **base,
        )


def resolve_markets(specs: Optional[list]) -> list:
    """Turn a list of specs (or Market objects) into Market objects. Defaults to 1x2."""
    if not specs:
        return [get_market("1x2")]
    return [s if isinstance(s, Market) else get_market(s) for s in specs]


def run_predictions(
    config: Config,
    fixtures: list[Fixture],
    models: Optional[list[ModelConfig]] = None,
    markets: Optional[list] = None,
    max_workers: int = 6,
    on_done: Optional[Callable[[Prediction], None]] = None,
) -> list[Prediction]:
    models = models or config.active_models()
    mkts = resolve_markets(markets)
    jobs = [(m, f, mk) for f in fixtures for mk in mkts for m in models]
    out: list[Prediction] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(predict_one, m, f, mk) for m, f, mk in jobs]
        for fut in cf.as_completed(futs):
            p = fut.result()
            out.append(p)
            if on_done:
                on_done(p)
    return out
