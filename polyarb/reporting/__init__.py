"""
Research reporting module.

The Backtester name is retained for compatibility but fails closed because
historical replay is not implemented or validated.
"""

from polyarb.reporting.performance_tracker import PerformanceTracker, PerformanceMetrics
from polyarb.reporting.report_generator import ReportGenerator
from polyarb.reporting.backtest import Backtester, BacktestResult

__all__ = [
    "PerformanceTracker",
    "PerformanceMetrics",
    "ReportGenerator",
    "Backtester",
    "BacktestResult",
]
