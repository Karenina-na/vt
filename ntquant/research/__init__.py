"""Research layer: factor evaluation across symbols and time windows."""
from ntquant.research.factors import SUPPORTED_FACTORS, build_strategy
from ntquant.research.runner import EvaluationResult, run_factor_evaluation
from ntquant.research.symbols import SUPPORTED_SYMBOLS, get_spec

__all__ = [
    "SUPPORTED_FACTORS",
    "SUPPORTED_SYMBOLS",
    "EvaluationResult",
    "build_strategy",
    "get_spec",
    "run_factor_evaluation",
]
