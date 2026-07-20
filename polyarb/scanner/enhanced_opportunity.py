"""
Enhanced opportunity representation for the scanner.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from polyarb.core.lifecycle import LifecycleState


class OpportunityClass(str, Enum):
    """Legacy classification of model-implied research candidates."""
    SINGLE_CONDITION = "single_condition"  # YES+NO Dutch-book
    NEGRISK_REBALANCING = "negrisk_rebalancing"  # Within-market rebalancing
    COMBINATORIAL = "combinatorial"  # Inter-market arbitrage
    SINGLE_EVENT_MULTI_MARKET = "single_event_multi_market"  # Multi-market coverage within an event
    TEMPLATE_BASED = "template_based"  # Strategy template (all_no, balanced)


class RiskLevel(str, Enum):
    """Research risk label; it is not a platform or financial risk rating."""
    LOW = "low"  # No material issue found within the tested model boundary.
    MEDIUM = "medium"  # Small residual risk or minor rule ambiguity
    HIGH = "high"  # Significant rule risk or execution complexity


@dataclass
class Leg:
    """Represents one modeled leg in a research candidate."""
    
    token_id: str
    side: str  # 'YES' or 'NO'
    outcome_label: str
    market_id: str
    market_question: str
    
    # Pricing
    price: float
    price_type: str  # 'ASK', 'BID', 'MID', 'LIVE', 'ACTUAL'
    size: Optional[float] = None  # Available liquidity
    
    # Spread/liquidity metrics
    spread_bps: Optional[float] = None
    depth: Optional[float] = None
    
    def __str__(self) -> str:
        return f"{self.side}({self.outcome_label}) @ {self.price:.4f}"


@dataclass
class EnhancedOpportunity:
    """
    Research opportunity with scanner metadata and an explicit lifecycle state.
    """
    
    # Identification
    id: str
    opportunity_class: OpportunityClass
    strategy_id: Optional[str] = None  # If from a strategy template
    
    # Description
    name: str = ""
    description: str = ""
    
    # Legs
    legs: List[Leg] = field(default_factory=list)
    
    # Financial metrics
    total_cost: float = 0.0
    worst_case_payoff: float = 0.0
    best_case_payoff: float = 0.0
    expected_profit: float = 0.0
    profit_percentage: float = 0.0
    
    # Adjusted for spreads and slippage
    adjusted_cost: Optional[float] = None
    adjusted_profit: Optional[float] = None
    adjusted_profit_percentage: Optional[float] = None
    
    # Risk assessment
    risk_level: RiskLevel = RiskLevel.MEDIUM
    rule_risk_notes: List[str] = field(default_factory=list)
    
    # Liquidity
    max_size: Optional[float] = None  # Max notional before significant slippage
    liquidity_score: Optional[float] = None  # 0-1 score
    
    # Markets involved
    market_ids: List[str] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    is_pure_arbitrage: bool = False  # Legacy field; false until external assumptions are verified.
    
    # Timestamps
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    lifecycle_state: LifecycleState = LifecycleState.DETECTED
    approved_at: Optional[datetime] = None
    reported_at: Optional[datetime] = None

    def approve(self) -> None:
        """Record approval state; execution also requires a RiskManager reservation."""
        self.lifecycle_state = LifecycleState.APPROVED
        self.approved_at = datetime.utcnow()

    def revoke_approval(self) -> None:
        """Return an unexecuted approval to detected state."""
        if self.lifecycle_state == LifecycleState.APPROVED:
            self.lifecycle_state = LifecycleState.DETECTED
            self.approved_at = None

    def mark_reported(self) -> None:
        """Record that the detected opportunity was included in a report."""
        self.lifecycle_state = LifecycleState.REPORTED
        self.reported_at = datetime.utcnow()
    
    def get_roi(self) -> float:
        """Backward-compatible alias for the model-implied edge percentage."""
        return self.profit_percentage
    
    def get_adjusted_roi(self) -> Optional[float]:
        """Backward-compatible alias for spread-adjusted model edge."""
        return self.adjusted_profit_percentage
    
    def get_leg_count(self) -> int:
        """Number of legs in the opportunity."""
        return len(self.legs)
    
    def get_markets(self) -> List[str]:
        """Get unique market IDs."""
        return list(set(self.market_ids))
    
    def is_high_quality(self, min_profit: float = 1.0, min_liquidity: float = 100) -> bool:
        """
        Check if opportunity meets quality thresholds.
        
        Args:
            min_profit: Minimum model-edge percentage
            min_liquidity: Minimum liquidity
            
        Returns:
            True if high quality
        """
        profit_ok = self.profit_percentage >= min_profit
        liquidity_ok = (self.max_size is None or self.max_size >= min_liquidity)
        risk_ok = self.risk_level != RiskLevel.HIGH
        
        return profit_ok and liquidity_ok and risk_ok
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "opportunity_class": self.opportunity_class.value,
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "legs": [
                {
                    "token_id": leg.token_id,
                    "side": leg.side,
                    "outcome_label": leg.outcome_label,
                    "price": leg.price,
                    "price_type": leg.price_type,
                }
                for leg in self.legs
            ],
            "total_cost": self.total_cost,
            "expected_profit": self.expected_profit,
            "profit_percentage": self.profit_percentage,
            "adjusted_profit_percentage": self.adjusted_profit_percentage,
            "risk_level": self.risk_level.value,
            "max_size": self.max_size,
            "market_ids": self.market_ids,
            "is_pure_arbitrage": self.is_pure_arbitrage,
            "lifecycle_state": self.lifecycle_state.value,
            "discovered_at": self.discovered_at.isoformat(),
        }
    
    def __str__(self) -> str:
        return (
            f"EnhancedOpportunity({self.opportunity_class.value}, "
            f"model_edge={self.profit_percentage:.2f}%, legs={len(self.legs)})"
        )
