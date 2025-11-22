"""
Base scanner class with common functionality.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, OpportunityClass
from polyarb.data.models import PriceType
from polyarb.data.price_accessor import PriceAccessor


@dataclass
class ScanResult:
    """Result of a scan operation."""
    
    opportunities: List[EnhancedOpportunity]
    scan_duration_ms: float
    markets_scanned: int
    timestamp: datetime
    price_type: PriceType
    
    def get_opportunity_count(self) -> int:
        """Get total number of opportunities found."""
        return len(self.opportunities)
    
    def filter_by_class(self, opp_class: OpportunityClass) -> List[EnhancedOpportunity]:
        """Filter opportunities by class."""
        return [o for o in self.opportunities if o.opportunity_class == opp_class]
    
    def get_top_opportunities(self, n: int = 10) -> List[EnhancedOpportunity]:
        """Get top N opportunities by profit percentage."""
        return sorted(
            self.opportunities,
            key=lambda o: o.profit_percentage,
            reverse=True
        )[:n]


class BaseScanner:
    """
    Base class for all scanner types.
    """
    
    def __init__(
        self,
        price_accessor: PriceAccessor,
        min_profit_threshold: float = 0.5,
        max_total_price_threshold: float = 0.98,
        price_type: PriceType = PriceType.ASK
    ):
        """
        Initialize base scanner.
        
        Args:
            price_accessor: Price accessor for fetching prices
            min_profit_threshold: Minimum profit percentage threshold
            max_total_price_threshold: Maximum total price for arb detection
            price_type: Default price type to use
        """
        self.price_accessor = price_accessor
        self.min_profit_threshold = min_profit_threshold
        self.max_total_price_threshold = max_total_price_threshold
        self.price_type = price_type
    
    async def scan(
        self,
        markets: List[Dict[str, Any]],
        **kwargs
    ) -> ScanResult:
        """
        Scan markets for opportunities.
        
        Must be implemented by subclasses.
        
        Args:
            markets: List of market dictionaries
            **kwargs: Additional scan parameters
            
        Returns:
            ScanResult with discovered opportunities
        """
        raise NotImplementedError("Subclasses must implement scan()")
    
    def calculate_profit_metrics(
        self,
        total_cost: float,
        worst_case_payoff: float,
        best_case_payoff: float
    ) -> Dict[str, float]:
        """
        Calculate profit metrics.
        
        Args:
            total_cost: Total cost of all legs
            worst_case_payoff: Minimum guaranteed payoff
            best_case_payoff: Maximum possible payoff
            
        Returns:
            Dictionary with profit metrics
        """
        expected_profit = worst_case_payoff - total_cost
        profit_percentage = (expected_profit / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_cost": total_cost,
            "worst_case_payoff": worst_case_payoff,
            "best_case_payoff": best_case_payoff,
            "expected_profit": expected_profit,
            "profit_percentage": profit_percentage,
        }
    
    def apply_spread_adjustment(
        self,
        total_cost: float,
        legs: List[Any],
        spread_multiplier: float = 1.0
    ) -> float:
        """
        Adjust cost for bid-ask spreads.
        
        Args:
            total_cost: Original total cost
            legs: List of legs with spread info
            spread_multiplier: Multiplier for spread impact
            
        Returns:
            Adjusted cost
        """
        spread_adjustment = 0.0
        
        for leg in legs:
            if hasattr(leg, 'spread_bps') and leg.spread_bps:
                # Spread impact as percentage
                spread_impact = leg.spread_bps / 10000 * leg.price
                spread_adjustment += spread_impact * spread_multiplier
        
        return total_cost + spread_adjustment
    
    def estimate_liquidity_score(self, legs: List[Any]) -> float:
        """
        Estimate overall liquidity score for opportunity.
        
        Args:
            legs: List of legs with depth info
            
        Returns:
            Liquidity score (0-1)
        """
        if not legs:
            return 0.0
        
        depths = []
        for leg in legs:
            if hasattr(leg, 'depth') and leg.depth:
                depths.append(leg.depth)
        
        if not depths:
            return 0.5  # Unknown, assume medium
        
        # Minimum depth across legs is limiting factor
        min_depth = min(depths)
        
        # Score based on depth thresholds
        if min_depth >= 1000:
            return 1.0
        elif min_depth >= 500:
            return 0.8
        elif min_depth >= 100:
            return 0.6
        elif min_depth >= 50:
            return 0.4
        else:
            return 0.2
    
    def is_opportunity_valid(
        self,
        profit_percentage: float,
        total_cost: float
    ) -> bool:
        """
        Check if opportunity meets basic validity criteria.
        
        Args:
            profit_percentage: Profit percentage
            total_cost: Total cost
            
        Returns:
            True if valid
        """
        # Must meet profit threshold
        if profit_percentage < self.min_profit_threshold:
            return False
        
        # Cost must be positive and reasonable
        if total_cost <= 0 or total_cost > 10:  # Max 10 per share
            return False
        
        return True
