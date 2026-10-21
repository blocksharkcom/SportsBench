"""Generate the bundled offline demo dataset across MULTIPLE markets, so
`sportsbench backtest --demo` shows 1x2, over/under goals, BTTS and corners —
with model personalities (sharp vs calibrated vs weak) coming through. Goal
markets use an analytic Poisson model so the 'true' probabilities are consistent
across markets; corners use a separate Poisson. Deterministic (seeded)."""
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
N = 200
MARGIN = 0.03
MARKET_SIGMA = 0.18
MARKETS = ["1x2", "ou_goals@2.5", "btts", "ou_corners@9.5"]

# (name, provider, est_sigma, fav_bias, conf_shift, error_rate)
MODELS = [
    ("GPT-5",           "openai",    0.07, 0.04, 0.02, 0.00),
    ("Claude Opus 4.8", "anthropic", 0.09, 0.00, -0.05, 0.00),
    ("Gemini 3 Pro",    "google",    0.13, 0.04, 0.01, 0.00),
    ("Grok 4",          "grok",      0.19, 0.11, 0.11, 0.00),
    ("DeepSeek V3",     "deepseek",  0.27, 0.15, 0.13, 0.015),
    ("Llama 3 (local)", "ollama",    0.35, 0.06, 0.06, 0.06),
]


def pois_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def sample_pois(lam):
    # Knuth's algorithm
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def goal_true(lh, la):
    ph = pd = pa = 0.0
    p_tot = [0.0] * 20
    byes = (1 - math.exp(-lh)) * (1 - math.exp(-la))
    for h in range(9):
        for a in range(9):
            p = pois_pmf(h, lh) * pois_pmf(a, la)
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
            if h + a < 20:
                p_tot[h + a] += p
    s = ph + pd + pa
    over25 = sum(p_tot[g] for g in range(3, 20))
    return {
        "1x2": {"home": ph / s, "draw": pd / s, "away": pa / s},
        "ou_goals@2.5": {"over": over25, "under": 1 - over25},
        "btts": {"yes": byes, "no": 1 - byes},
    }


def corners_true(lc, line=9.5):
    over = sum(pois_pmf(k, lc) for k in range(int(line) + 1, 40))
    return {"over": over, "under": 1 - over}


def perturb(prob, sigma):
    ks = list(prob)
    e = [math.exp(math.log(max(1e-4, prob[k])) + random.gauss(0, sigma)) for k in ks]
    s = sum(e)
    return {k: e[i] / s for i, k in enumerate(ks)}


def book_odds(prob, margin=MARGIN):
    # clamp to realistic prices — no book hangs <= 1.01
    return {k: max(1.02, round(1.0 / (p * (1 + margin)), 2)) for k, p in prob.items()}


fixtures, results, predictions = [], [], []

for i in range(N):
    home, away = random.sample(TEAMS, 2)
    lh = max(0.3, random.gauss(1.6, 0.5))    # expected home goals
    la = max(0.3, random.gauss(1.1, 0.45))   # expected away goals
    lc = max(4.0, random.gauss(10.2, 2.0))   # expected total corners

    true = goal_true(lh, la)
    true["ou_corners@9.5"] = corners_true(lc, 9.5)

    markets_odds, closing_odds, market_true = {}, {}, {}
    for spec in MARKETS:
        mkt = perturb(true[spec], MARKET_SIGMA)
        market_true[spec] = mkt
        markets_odds[spec] = book_odds(mkt)
        closing_odds[spec] = book_odds(perturb(mkt, 0.05))

    fid = f"demo-{i+1:03d}"
    fixtures.append({
        "id": fid, "sport": "football", "league": "Demo Premier League",
        "home": home, "away": away,
        "kickoff": f"2026-0{(i % 9)+1}-{(i % 27)+1:02d}T15:00:00+00:00",
        "status": "finished",
        "odds": markets_odds["1x2"], "closing_odds": closing_odds["1x2"],
        "markets": markets_odds, "closing_markets": closing_odds,
    })

    hs, as_, corners = sample_pois(lh), sample_pois(la), sample_pois(lc)
    hc = round(corners * 0.55)
    results.append({
        "fixture_id": fid, "home_score": hs, "away_score": as_,
        "stats": {"home": {"corners": hc}, "away": {"corners": corners - hc}},
    })

    for name, prov, sigma, favbias, conf_shift, erate in MODELS:
        skill = max(0.05, min(0.85, (0.40 - sigma) / 0.40))
        w = skill * 0.6
        for spec in MARKETS:
            mkt, tru, od = market_true[spec], true[spec], markets_odds[spec]
            if random.random() < erate:
                predictions.append({
                    "fixture_id": fid, "model": name, "provider": prov, "market": spec,
                    "pick": "", "probs": {k: 0 for k in mkt}, "confidence": 0.0,
                    "rationale": "", "odds_at_pick": od,
                    "error": "ProviderError: 402 insufficient credits",
                })
                continue
            base = {k: (1 - w) * mkt[k] + w * tru[k] for k in mkt}
            est = perturb(base, 0.03 + (1 - skill) * 0.14)
            fav = min(est, key=lambda k: od.get(k, 99))
            est[fav] = est[fav] + favbias * (1 - est[fav])
            s = sum(est.values())
            est = {k: round(v / s, 4) for k, v in est.items()}
            pick = max(est, key=est.get)
            conf = min(0.97, max(0.34, est[pick] + conf_shift))
            predictions.append({
                "fixture_id": fid, "model": name, "provider": prov, "market": spec,
                "pick": pick, "probs": est, "confidence": round(conf, 3),
                "rationale": "demo", "odds_at_pick": od, "error": None,
            })

(OUT / "demo_fixtures.json").write_text(json.dumps(fixtures, indent=2))
(OUT / "demo_results.json").write_text(json.dumps(results, indent=2))
(OUT / "demo_predictions.json").write_text(json.dumps(predictions, indent=2))
print(f"wrote {len(fixtures)} fixtures, {len(results)} results, {len(predictions)} predictions "
      f"across {len(MARKETS)} markets")
