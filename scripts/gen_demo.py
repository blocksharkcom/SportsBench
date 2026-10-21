"""Generate the bundled offline demo dataset: fixtures (+odds, +closing odds),
results, and pre-made predictions from several 'models' with distinct skill and
bias so the leaderboard tells a realistic, compelling story (a sharp model beats
the market, a calibrated one tops Brier, weak/cheap ones bleed, one errors out).

Realism note: the bookmaker price is a *noisy* estimate of the truth plus a
margin — so edge only exists where a model's estimate is sharper than the market.
Deterministic (seeded)."""
import json
import math
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "src" / "sportsbench" / "data"
OUT.mkdir(parents=True, exist_ok=True)

TEAMS = [
    "Arsenal", "Man City", "Liverpool", "Chelsea", "Tottenham", "Man United",
    "Newcastle", "Aston Villa", "Brighton", "West Ham", "Everton", "Fulham",
    "Brentford", "Wolves", "Bournemouth", "Crystal Palace", "Nottingham Forest",
    "Luton", "Burnley", "Sheffield United",
]
N = 300
MARGIN = 0.03  # ~3% bookmaker overround


def softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return [v / s for v in e]


def perturb(probs, sigma):
    """Nudge a probability vector in log-space, then renormalise."""
    logits = [math.log(max(1e-4, p)) + random.gauss(0, sigma) for p in probs]
    return softmax(logits)


def book_odds(market_probs, margin=MARGIN):
    """Odds a book would hang: implied = fair probability inflated by the margin
    (so flat-betting is -EV by the margin, and value only exists where a model is
    genuinely sharper than the market)."""
    return {k: round(1.0 / (pi * (1 + margin)), 2) for k, pi in
            zip(("home", "draw", "away"), market_probs)}


# model personalities: (name, provider, est_sigma, fav_bias, conf_shift, error_rate)
# lower est_sigma == sharper estimate of the truth. market sigma is 0.20, so a
# model sharper than the market (sigma < 0.20) can find genuine value.
MODELS = [
    ("GPT-5",           "openai",    0.07, 0.04, 0.02, 0.00),  # sharpest, finds value
    ("Claude Opus 4.8", "anthropic", 0.09, 0.00, -0.05, 0.00),  # best calibrated
    ("Gemini 3 Pro",    "google",    0.13, 0.04, 0.01, 0.00),
    ("Grok 4",          "grok",      0.19, 0.11, 0.11, 0.00),  # overconfident
    ("DeepSeek V3",     "deepseek",  0.27, 0.15, 0.13, 0.015),  # weak, bleeds
    ("Llama 3 (local)", "ollama",    0.35, 0.06, 0.06, 0.06),  # weakest + errors
]
MARKET_SIGMA = 0.20

fixtures, results, predictions = [], [], []

for i in range(N):
    home, away = random.sample(TEAMS, 2)
    # latent strengths -> TRUE outcome probabilities (with a home edge).
    # Wider spread => more decisive favourites => clearer skill separation.
    sh, sa = random.gauss(0.35, 1.1), random.gauss(0, 1.1)
    ph, pa = softmax([sh, sa])
    pd = 0.25 + random.uniform(-0.04, 0.04)
    tot = ph + pa + pd
    true = [ph / tot, pd / tot, pa / tot]  # home, draw, away

    # the market: a noisy read of the truth, then margin applied
    market = perturb(true, MARKET_SIGMA)
    odds = book_odds(market)
    closing = book_odds(perturb(market, 0.05))  # closing drifts a touch

    fid = f"demo-{i+1:02d}"
    fixtures.append({
        "id": fid, "sport": "football", "league": "Demo Premier League",
        "home": home, "away": away,
        "kickoff": f"2026-0{(i % 9)+1}-{(i % 27)+1:02d}T15:00:00+00:00",
        "status": "finished", "odds": odds, "closing_odds": closing,
    })

    # realise a result by sampling the TRUE distribution
    r = random.random()
    outcome = "home" if r < true[0] else ("draw" if r < true[0] + true[1] else "away")
    if outcome == "home":
        hs, as_ = random.randint(1, 3), random.randint(0, 1)
    elif outcome == "away":
        hs, as_ = random.randint(0, 1), random.randint(1, 3)
    else:
        g = random.randint(0, 2); hs = as_ = g
    results.append({"fixture_id": fid, "home_score": hs, "away_score": as_})

    for name, prov, sigma, favbias, conf_shift, erate in MODELS:
        if random.random() < erate:
            predictions.append({
                "fixture_id": fid, "model": name, "provider": prov, "pick": "",
                "probs": {"home": 0, "draw": 0, "away": 0}, "confidence": 0.0,
                "rationale": "", "odds_at_pick": odds,
                "error": "ProviderError: 402 insufficient credits",
            })
            continue
        # Real models anchor on the market and lean toward the truth by their skill
        # — so most picks match the market (few value bets) and only a sharp model
        # has a genuine, sparse edge. Weak models add big noise => noisy, wrong bets.
        skill = max(0.05, min(0.85, (0.40 - sigma) / 0.40))
        w = skill * 0.6  # how far toward the truth they pull from the market line
        base = [(1 - w) * mk + w * tr for mk, tr in zip(market, true)]
        est = perturb(base, 0.03 + (1 - skill) * 0.14)
        # a mild favourite bias nudges weight toward the shorter price
        fav = min(range(3), key=lambda k: odds[("home", "draw", "away")[k]])
        est[fav] += favbias * (1 - est[fav])
        s = sum(est)
        est = [p / s for p in est]
        probs = {"home": round(est[0], 4), "draw": round(est[1], 4), "away": round(est[2], 4)}
        pick = max(probs, key=probs.get)
        conf = min(0.97, max(0.34, probs[pick] + conf_shift))
        predictions.append({
            "fixture_id": fid, "model": name, "provider": prov, "pick": pick,
            "probs": probs, "confidence": round(conf, 3), "rationale": "demo",
            "odds_at_pick": odds, "error": None,
        })

(OUT / "demo_fixtures.json").write_text(json.dumps(fixtures, indent=2))
(OUT / "demo_results.json").write_text(json.dumps(results, indent=2))
(OUT / "demo_predictions.json").write_text(json.dumps(predictions, indent=2))
print(f"wrote {len(fixtures)} fixtures, {len(results)} results, {len(predictions)} predictions")
