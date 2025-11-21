"""
Evaluation, Backtesting & Reporting Module.

This module provides performance analytics, backtesting, and report generation.
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
