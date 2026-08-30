"""Research layer: factor evaluation across symbols and time windows."""
from ntquant.research.factors import SUPPORTED_FACTORS, build_factor, canonical
from ntquant.research.runner import EvaluationResult, run_factor_evaluation
from ntquant.research.symbols import SUPPORTED_SYMBOLS, get_spec

__all__ = [
    "SUPPORTED_FACTORS",
    "SUPPORTED_SYMBOLS",
    "EvaluationResult",
    "build_factor",
    "canonical",
    "get_spec",
    "run_factor_evaluation",
]
