"""SportsBench — the open benchmark for LLM sports prediction.

Can GPT-5, Claude, Gemini and Grok actually beat the bookmakers? Run it yourself,
graded in public. https://modelfights.com
"""
__version__ = "0.1.0"

from .types import Fixture, Prediction, Result, Odds
from .config import Config, ModelConfig
from .engine import run_predictions, predict_one
from .grading import score_predictions, rank
from .value import find_value, consensus

__all__ = [
    "__version__",
    "Fixture", "Prediction", "Result", "Odds",
    "Config", "ModelConfig",
    "run_predictions", "predict_one",
    "score_predictions", "rank",
    "find_value", "consensus",
]
