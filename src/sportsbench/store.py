"""Local SQLite store — zero-config persistence so runs accumulate into a record."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .types import Fixture, Prediction, Result

DEFAULT_PATH = "sportsbench.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
  id TEXT PRIMARY KEY, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
  fixture_id TEXT, model TEXT, data TEXT NOT NULL,
  PRIMARY KEY (fixture_id, model)
);
CREATE TABLE IF NOT EXISTS results (
  fixture_id TEXT PRIMARY KEY, data TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # fixtures
    def save_fixtures(self, fixtures: list[Fixture]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO fixtures (id, data) VALUES (?, ?)",
            [(f.id, json.dumps(f.to_dict())) for f in fixtures],
        )
        self.db.commit()

    def fixtures(self) -> list[Fixture]:
        rows = self.db.execute("SELECT data FROM fixtures").fetchall()
        return [Fixture.from_dict(json.loads(r[0])) for r in rows]

    # predictions
    def save_predictions(self, preds: list[Prediction]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO predictions (fixture_id, model, data) VALUES (?, ?, ?)",
            [(p.fixture_id, p.model, json.dumps(p.to_dict())) for p in preds],
        )
        self.db.commit()

    def predictions(self) -> list[Prediction]:
        rows = self.db.execute("SELECT data FROM predictions").fetchall()
        return [Prediction.from_dict(json.loads(r[0])) for r in rows]

    # results
    def save_results(self, results: dict[str, Result]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO results (fixture_id, data) VALUES (?, ?)",
            [(fid, json.dumps(r.to_dict())) for fid, r in results.items()],
        )
        self.db.commit()

    def results(self) -> dict[str, Result]:
        rows = self.db.execute("SELECT data FROM results").fetchall()
        out = {}
        for (d,) in rows:
            j = json.loads(d)
            out[j["fixture_id"]] = Result(j["fixture_id"], j["home_score"], j["away_score"])
        return out

    def close(self) -> None:
        self.db.close()
