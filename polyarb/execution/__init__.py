"""
Execution & Risk Management Module.

This module handles simulated execution, slippage inputs, and risk controls.
Live order submission is disabled and not implemented.
"""

from polyarb.execution.basket_executor import (
    BasketExecutor,
    ExecutionMode,
    ExecutionResult,
    ExecutionStatus,
    LiveExecutionDisabledError,
    OpportunityNotApprovedError,
)
from polyarb.execution.risk_manager import RiskManager, RiskLimits
from polyarb.execution.rule_analyzer import RuleRiskAnalyzer

__all__ = [
    "BasketExecutor",
    "ExecutionMode",
    "ExecutionResult",
    "ExecutionStatus",
    "LiveExecutionDisabledError",
    "OpportunityNotApprovedError",
    "RiskManager",
    "RiskLimits",
    "RuleRiskAnalyzer",
]
