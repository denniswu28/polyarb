"""
Arbitrage opportunity representation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class OpportunityType(Enum):
    """Types of arbitrage opportunities."""
    
    INTRA_PLATFORM = "intra_platform"  # Arbitrage within same platform
    CROSS_PLATFORM = "cross_platform"  # Arbitrage across different platforms


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    
    opportunity_type: OpportunityType
    market_ids: List[str]  # IDs of markets involved
    platforms: List[str]  # Platforms involved
    description: str  # Human-readable description
    profit_percentage: float  # Expected profit as percentage
    strategy: Dict[str, any]  # Strategy details (positions to take)
    confidence: float = 1.0  # Confidence score (0-1)
    
    def __repr__(self) -> str:
        """String representation of the opportunity."""
        return (
            f"ArbitrageOpportunity(type={self.opportunity_type.value}, "
            f"profit={self.profit_percentage:.2f}%, "
            f"platforms={','.join(self.platforms)}, "
            f"confidence={self.confidence:.2f})"
        )
    
    def is_profitable(self, min_profit_threshold: float = 0.0) -> bool:
        """
        Check if opportunity meets minimum profit threshold.
        
        Args:
            min_profit_threshold: Minimum profit percentage required
            
        Returns:
            True if opportunity is profitable enough
        """
        return self.profit_percentage >= min_profit_threshold
