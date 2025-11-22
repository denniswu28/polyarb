"""
Execution & Risk Management Module.

This module handles order execution, slippage tracking, and risk controls
for arbitrage opportunities.
"""

from polyarb.execution.basket_executor import BasketExecutor, ExecutionResult
from polyarb.execution.risk_manager import RiskManager, RiskLimits
from polyarb.execution.rule_analyzer import RuleRiskAnalyzer

__all__ = [
    "BasketExecutor",
    "ExecutionResult",
    "RiskManager",
    "RiskLimits",
    "RuleRiskAnalyzer",
]
