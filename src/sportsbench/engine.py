"""The engine: give every model the same locked brief, collect predictions.

Errors are recorded on the prediction (never hidden) — a model that fails or runs
out of credit shows up as an error row, exactly like the public record on the site.
"""
from __future__ import annotations

import concurrent.futures as cf
from typing import Callable, Optional

from .brief import SYSTEM, build_user_prompt, normalise_probs, market_for
from .config import Config, ModelConfig
from .proof import prompt_hash
from .providers import build_provider, extract_json, ProviderError
from .types import Fixture, Prediction


def predict_one(mc: ModelConfig, fixture: Fixture) -> Prediction:
    user = build_user_prompt(fixture)
    phash = prompt_hash(SYSTEM, user)
    market = market_for(fixture)
    base = dict(
        fixture_id=fixture.id, model=mc.name, provider=mc.provider,
        odds_at_pick=fixture.odds.to_dict() if fixture.odds else None,
        prompt_sha256=phash,
    )
    try:
        provider = build_provider(mc)
        raw = provider.complete(SYSTEM, user)
        data = extract_json(raw)
        probs = normalise_probs(data.get("probs", {}), market)
        pick = data.get("pick")
        if pick not in market:
            pick = max(probs, key=probs.get)
        conf = float(data.get("confidence", probs.get(pick, 0.0)))
        return Prediction(
            pick=pick, probs=probs, confidence=max(0.0, min(1.0, conf)),
            rationale=str(data.get("rationale", ""))[:400], **base,
        )
    except (ProviderError, Exception) as e:  # recorded, not fatal
        return Prediction(
            pick="", probs={m: 0.0 for m in market}, confidence=0.0,
            rationale="", error=f"{type(e).__name__}: {e}", **base,
        )


def run_predictions(
    config: Config,
    fixtures: list[Fixture],
    models: Optional[list[ModelConfig]] = None,
    max_workers: int = 6,
    on_done: Optional[Callable[[Prediction], None]] = None,
) -> list[Prediction]:
    models = models or config.active_models()
    jobs = [(m, f) for f in fixtures for m in models]
    out: list[Prediction] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(predict_one, m, f): (m, f) for m, f in jobs}
        for fut in cf.as_completed(futs):
            p = fut.result()
            out.append(p)
            if on_done:
                on_done(p)
    return out
