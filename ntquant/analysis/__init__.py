"""Analysis layer: reports, performance stats, and visualization."""
from ntquant.analysis.reports import generate_all_reports
from ntquant.analysis.stats import performance_summary, summary_frame
from ntquant.analysis.visuals import make_tearsheet

__all__ = ["generate_all_reports", "performance_summary", "summary_frame", "make_tearsheet"]
