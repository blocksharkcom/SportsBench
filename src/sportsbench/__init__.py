"""SportsBench — the open benchmark for LLM sports prediction.

Can GPT-5, Claude, Gemini and Grok actually beat the bookmakers? Run it yourself,
graded in public. https://modelfights.com
"""
__version__ = "0.2.0"

from .types import Fixture, Prediction, Result, Odds
from .config import Config, ModelConfig
from .markets import Market, Selection, get_market, available, markets_for_sport
from .engine import run_predictions, predict_one
from .grading import score_predictions, rank
from .value import find_value, consensus
from . import sources

__all__ = [
    "__version__",
    "Fixture", "Prediction", "Result", "Odds",
    "Config", "ModelConfig",
    "Market", "Selection", "get_market", "available", "markets_for_sport",
    "run_predictions", "predict_one",
    "score_predictions", "rank",
    "find_value", "consensus",
    "sources",
]
