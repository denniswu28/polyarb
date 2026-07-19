"""
Arbitrage opportunity representation.
"""

from dataclasses import dataclass
from typing import Dict, List
from enum import Enum

from polyarb.core.lifecycle import LifecycleState


class OpportunityType(Enum):
    """Legacy categories for model-implied research candidates."""
    
    INTRA_PLATFORM = "intra_platform"  # Arbitrage within same platform
    CROSS_PLATFORM = "cross_platform"  # Arbitrage across different platforms


@dataclass
class ArbitrageOpportunity:
    """Represents a detected research candidate."""
    
    opportunity_type: OpportunityType
    market_ids: List[str]  # IDs of markets involved
    platforms: List[str]  # Platforms involved
    description: str  # Human-readable description
    profit_percentage: float  # Backward-compatible name for model-implied edge percentage
    strategy: Dict[str, any]  # Strategy details (positions to take)
    confidence: float = 0.0  # Legacy, uncalibrated field; no confidence claim is supported.
    lifecycle_state: LifecycleState = LifecycleState.DETECTED
    
    def __repr__(self) -> str:
        """String representation of the opportunity."""
        return (
            f"ArbitrageOpportunity(type={self.opportunity_type.value}, "
            f"model_edge={self.profit_percentage:.2f}%, "
            f"platforms={','.join(self.platforms)}, "
            f"uncalibrated_confidence={self.confidence:.2f})"
        )
    
    def is_profitable(self, min_profit_threshold: float = 0.0) -> bool:
        """
        Check whether the candidate meets the legacy model-edge threshold.
        
        Args:
            min_profit_threshold: Minimum model-implied edge percentage required
            
        Returns:
            True if the candidate's modeled edge meets the threshold
        """
        return self.profit_percentage >= min_profit_threshold
