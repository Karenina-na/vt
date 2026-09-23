"""Research layer: factor evaluation across symbols and time windows."""
from ntquant.research.runner import EvaluationResult, run_factor_evaluation
from ntquant.research.symbols import SUPPORTED_SYMBOLS, get_spec

__all__ = [
    "SUPPORTED_SYMBOLS",
    "EvaluationResult",
    "get_spec",
    "run_factor_evaluation",
]
