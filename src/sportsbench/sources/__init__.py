from .base import FixtureSource
from .files import JSONSource, DemoSource, read_fixtures_csv

__all__ = ["FixtureSource", "JSONSource", "DemoSource", "read_fixtures_csv", "get_source"]


def get_source(name: str, **kwargs) -> FixtureSource:
    name = (name or "demo").lower()
    if name in ("demo", "sample"):
        return DemoSource()
    if name in ("json", "file"):
        return JSONSource(kwargs["fixtures_path"], kwargs.get("results_path"))
    if name in ("football-data", "football-data.org", "footballdata"):
        from .footballdata import FootballDataSource
        return FootballDataSource(kwargs.get("api_key"))
    if name in ("pro", "live", "modelfights"):
        from ..pro import ProLiveSource
        return ProLiveSource(kwargs.get("client"))
    raise ValueError(f"unknown source: {name}")
