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
from ..grading import rank, score_predictions
from ..markets import DEFAULT_MARKETS, get_market
from ..sources.files import DemoSource, _read_json
from ..types import Prediction


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

    def log_message(self, *a):  # quiet
        pass

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
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, _page(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._json(200, self._state())
            if u.path == "/api/demo":
                return self._json(200, {"leaderboards": _demo_leaderboards()})
            return self._json(404, {"error": "not found"})
        except Exception as e:  # never crash the dev server
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

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
