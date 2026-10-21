"""`sportsbench serve` — a local dark-themed dashboard for reading data and running
models, with zero extra dependencies (Python stdlib http.server only).

Everything stays local: your API keys never leave the machine. The UI is a single
self-contained page that talks to a small local JSON API backed by the same core
the CLI uses (config, engine, markets, grading, value).
"""
from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from .. import __version__
from ..config import Config
from ..engine import run_predictions
from ..grading import rank, score_predictions
from ..markets import DEFAULT_MARKETS, get_market
from ..sources.files import DemoSource, _read_json
from ..types import Prediction
from ..value import consensus, find_value


def _page() -> str:
    with resources.as_file(resources.files("sportsbench.webui")) as d:
        return (d / "index.html").read_text()


def _demo_leaderboards() -> list:
    src = DemoSource()
    fixtures = src.upcoming(limit=5000)
    results = src.results([f.id for f in fixtures])
    fxmap = {f.id: f for f in fixtures}
    with resources.as_file(resources.files("sportsbench.data")) as d:
        preds = [Prediction.from_dict(x) for x in _read_json(str(d / "demo_predictions.json"))]
    scores = score_predictions(preds, results, fixtures=fxmap)
    specs: list = []
    for s in scores:
        if s.market not in specs:
            specs.append(s.market)
    out = []
    for spec in specs:
        rows = [s.to_row() for s in rank([s for s in scores if s.market == spec], by="brier")]
        out.append({"market": spec, "name": get_market(spec).name, "rows": rows})
    return out


class _Handler(BaseHTTPRequestHandler):
    cfg: Config = None  # type: ignore[assignment]
    port: int = 8787

    def log_message(self, *a):  # quiet
        pass

    def _guard(self) -> bool:
        """Defend a local server against malicious web pages: reject requests
        whose Host isn't our loopback address (DNS-rebinding) or whose Origin is
        cross-site (CSRF). This also closes the only cross-origin SSRF vector —
        a page can't make us call our data sources with the user's keys."""
        p = _Handler.port
        hosts = {f"127.0.0.1:{p}", f"localhost:{p}", f"[::1]:{p}"}
        host = (self.headers.get("Host") or "").lower()
        if host and host not in hosts:
            self._json(403, {"error": "forbidden_host"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin.lower() not in {f"http://{h}" for h in hosts}:
            self._json(403, {"error": "cross_origin_blocked"})
            return False
        return True

    def _send(self, code: int, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj))

    def do_GET(self):
        if not self._guard():
            return
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, _page(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._json(200, self._state())
            if u.path == "/api/demo":
                return self._json(200, {"leaderboards": _demo_leaderboards()})
            if u.path == "/api/fixtures":
                return self._json(200, self._fixtures(parse_qs(u.query)))
            if u.path == "/api/leaderboard":
                return self._json(200, {"leaderboards": self._store_leaderboards()})
            return self._json(404, {"error": "not found"})
        except Exception as e:  # never crash the dev server
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._guard():
            return
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            if u.path == "/api/run":
                return self._json(200, self._run(body))
            return self._json(404, {"error": "not found"})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _source(self, name: str):
        from ..sources import get_source
        cfg = _Handler.cfg or Config.load()
        if name in ("modelfights", "mf", "pro", "live"):
            from ..pro import ModelFightsClient
            return get_source("modelfights", client=ModelFightsClient(cfg))
        return get_source(name)

    def _fixtures(self, q: dict) -> dict:
        name = (q.get("source", ["demo"])[0])
        league = q.get("league", [None])[0] or None
        limit = min(100, max(1, int(q.get("limit", ["25"])[0])))
        fx = self._source(name).upcoming(league, limit)
        return {"fixtures": [{
            "id": f.id, "label": f.label(), "league": f.league, "kickoff": f.kickoff,
            "sport": f.sport, "markets": list((f.markets or {}).keys()),
        } for f in fx]}

    def _store_leaderboards(self) -> list:
        from ..store import Store
        st = Store("sportsbench.db")
        preds = st.predictions()
        if not preds:
            return []
        fxmap = {f.id: f for f in st.fixtures()}
        scores = score_predictions(preds, st.results(), fixtures=fxmap)
        specs: list = []
        for s in scores:
            if s.market not in specs:
                specs.append(s.market)
        out = []
        for spec in specs:
            rows = [s.to_row() for s in rank([s for s in scores if s.market == spec], by="roi")]
            try:
                name = get_market(spec).name
            except Exception:
                name = spec
            out.append({"market": spec, "name": name, "rows": rows})
        return out

    def _run(self, body: dict) -> dict:
        cfg = _Handler.cfg or Config.load()
        name = body.get("source", "demo")
        fid = body.get("fixture_id")
        league = body.get("league")
        src = self._source(name)
        fixtures = src.upcoming(league, 100)
        fx = next((f for f in fixtures if f.id == fid), None)
        if fx is None:
            return {"error": "fixture not found"}
        specs = body.get("markets") or cfg.market_specs(fx.sport)
        if not cfg.active_models():
            return {"error": "no models configured — run `sportsbench init` and add API keys"}
        preds = run_predictions(cfg, [fx], markets=specs)

        markets_out = []
        for spec in specs:
            mk = get_market(spec)
            keys = mk.selection_keys()
            mpreds = [p for p in preds if (p.market or "1x2") == spec]
            rows = []
            for p in sorted(mpreds, key=lambda x: (x.error is not None, -x.confidence)):
                if p.error:
                    rows.append({"model": p.model, "error": p.error[:90]})
                else:
                    rows.append({"model": p.model, "pick": mk.label_for(p.pick),
                                 "p": round(p.probs.get(p.pick, 0.0), 3),
                                 "conf": round(p.confidence, 2), "why": p.rationale})
            cons = consensus([p for p in mpreds if not p.error], keys)
            cpick = max(cons, key=cons.get) if any(cons.values()) else None
            bets = find_value([fx], preds, market=spec, min_edge=0.02,
                              kelly_fraction=cfg.kelly_fraction, devig_method=cfg.devig, source="consensus")
            markets_out.append({
                "spec": spec, "name": mk.name, "odds": fx.market_odds(spec) or {}, "rows": rows,
                "consensus": ({"pick": mk.label_for(cpick), "p": round(cons[cpick], 3)} if cpick else None),
                "value": [{"label": b.label, "model_prob": b.model_prob, "fair_prob": b.fair_prob,
                           "odds": b.decimal_odds, "edge": b.edge, "kelly": b.kelly} for b in bets],
            })
        return {"fixture": {"label": fx.label(), "league": fx.league, "kickoff": fx.kickoff},
                "markets": markets_out}

    def _state(self) -> dict:
        cfg = _Handler.cfg or Config.load()
        return {
            "version": __version__,
            "sport": cfg.sport,
            "modelfights_key": bool(cfg.modelfights.api_key()),
            "markets": DEFAULT_MARKETS,
            "models": [
                {"name": m.name, "provider": m.provider, "model": m.model, "has_key": bool(m.api_key())}
                for m in cfg.models
            ],
        }


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = True,
          config: Config | None = None) -> None:
    _Handler.cfg = config or Config.load()
    _Handler.port = port
    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}"
    print(f"SportsBench dashboard → {url}   (Ctrl-C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
