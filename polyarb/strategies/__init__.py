"""
Strategy Template Library.

This module provides reusable arbitrage and hedge strategy templates,
including 'all_no', 'balanced', and custom strategies.
"""

from polyarb.strategies.base import (
    Strategy,
    StrategyMethod,
    StrategyPosition,
    LogicalSpec,
)
from polyarb.strategies.registry import StrategyRegistry
from polyarb.strategies.templates import (
    create_all_no_strategy,
    create_balanced_strategy,
    create_custom_strategy,
)

__all__ = [
    "Strategy",
    "StrategyMethod",
    "StrategyPosition",
    "LogicalSpec",
    "StrategyRegistry",
    "create_all_no_strategy",
    "create_balanced_strategy",
    "create_custom_strategy",
]
