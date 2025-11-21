"""
Base classes for strategy templates.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


class StrategyMethod(str, Enum):
    """Strategy template methods."""
    ALL_NO = "all_no"  # Buy NO on mutually exclusive outcomes
    BALANCED = "balanced"  # Two complementary baskets A/B
    CUSTOM = "custom"  # Custom strategy


class StrategyType(str, Enum):
    """Strategy classification."""
    PURE_LOGICAL = "pure_logical"  # Pure arbitrage, all paths profitable
    HIGH_PROB_HEDGE = "high_prob_hedge"  # Small residual risk
    DIRECTIONAL = "directional"  # Speculative, not arbitrage


@dataclass
class StrategyPosition:
    """
    Represents a position within a strategy.
    """
    event_id: str
    event_slug: str
    market_id: str
    market_slug: str
    outcome_label: str
    outcome_id: str  # condition_id
    token_id: str  # YES or NO token ID
    side: str  # 'YES' or 'NO'
    
    # Optional metadata
    price: Optional[float] = None
    size: Optional[float] = None
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.side}({self.outcome_label}) in {self.market_slug}"


@dataclass
class LogicalSpec:
    """
    Logical specification describing payoff structure.
    
    This describes which positions pay off in which outcome scenarios.
    """
    description: str  # Human-readable explanation
    scenarios: List[Dict[str, Any]]  # List of outcome scenarios
    worst_case_payoff: float  # Minimum guaranteed payoff
    best_case_payoff: float  # Maximum possible payoff
    
    # For pure arbitrage, worst_case_payoff should be >= investment
    # For hedges, worst_case_payoff may be < investment (residual risk)


@dataclass
class Strategy:
    """
    Represents an arbitrage or hedge strategy.
    """
    id: str  # Unique identifier
    name: str
    subtitle: str
    method: StrategyMethod
    strategy_type: StrategyType = StrategyType.PURE_LOGICAL
    
    # Positions
    positions: List[StrategyPosition] = field(default_factory=list)
    
    # For balanced strategies, split into two sides
    side_a_positions: List[StrategyPosition] = field(default_factory=list)
    side_b_positions: List[StrategyPosition] = field(default_factory=list)
    
    # Logical specification
    logical_spec: Optional[LogicalSpec] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_all_positions(self) -> List[StrategyPosition]:
        """Get all positions in the strategy."""
        if self.method == StrategyMethod.BALANCED:
            return self.side_a_positions + self.side_b_positions
        else:
            return self.positions
    
    def get_position_count(self) -> int:
        """Get total number of positions."""
        return len(self.get_all_positions())
    
    def get_markets(self) -> List[str]:
        """Get unique market IDs involved in strategy."""
        return list(set(pos.market_id for pos in self.get_all_positions()))
    
    def get_events(self) -> List[str]:
        """Get unique event IDs involved in strategy."""
        return list(set(pos.event_id for pos in self.get_all_positions()))
    
    def is_pure_arbitrage(self) -> bool:
        """Check if this is pure arbitrage (no residual risk)."""
        return self.strategy_type == StrategyType.PURE_LOGICAL
    
    def __str__(self) -> str:
        """String representation."""
        return (
            f"Strategy({self.name}, method={self.method.value}, "
            f"type={self.strategy_type.value}, positions={self.get_position_count()})"
        )


def validate_strategy(strategy: Strategy) -> tuple[bool, List[str]]:
    """
    Validate a strategy for consistency.
    
    Args:
        strategy: Strategy to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check positions exist
    all_positions = strategy.get_all_positions()
    if not all_positions:
        errors.append("Strategy must have at least one position")
    
    # Check method-specific requirements
    if strategy.method == StrategyMethod.ALL_NO:
        # All positions should be NO side
        for pos in all_positions:
            if pos.side != "NO":
                errors.append(f"ALL_NO strategy should only have NO positions, found {pos.side}")
    
    elif strategy.method == StrategyMethod.BALANCED:
        # Should have positions on both sides
        if not strategy.side_a_positions:
            errors.append("BALANCED strategy missing side_a_positions")
        if not strategy.side_b_positions:
            errors.append("BALANCED strategy missing side_b_positions")
    
    # Check logical spec if present
    if strategy.logical_spec:
        if strategy.logical_spec.worst_case_payoff > strategy.logical_spec.best_case_payoff:
            errors.append("Worst case payoff cannot exceed best case payoff")
    
    return len(errors) == 0, errors
