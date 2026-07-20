"""
Base scanner class with common functionality.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import math

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
        """Get top N candidates by the legacy model-edge percentage field."""
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
        price_type: PriceType = PriceType.ASK,
        fee_rate_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ):
        """
        Initialize base scanner.
        
        Args:
            price_accessor: Price accessor for fetching prices
            min_profit_threshold: Minimum model-implied edge percentage
            max_total_price_threshold: Maximum total price for arb detection
            price_type: Default price type to use
            fee_rate_bps: Explicit per-basket fee assumption in basis points
            slippage_bps: Explicit per-basket slippage assumption in basis points
        """
        min_profit_threshold = self._finite_float(
            min_profit_threshold,
            "min_profit_threshold",
        )
        max_total_price_threshold = self._finite_float(
            max_total_price_threshold,
            "max_total_price_threshold",
        )
        fee_rate_bps = self._finite_float(fee_rate_bps, "fee_rate_bps")
        slippage_bps = self._finite_float(slippage_bps, "slippage_bps")
        if fee_rate_bps < 0 or slippage_bps < 0:
            raise ValueError("fee_rate_bps and slippage_bps must be non-negative")
        self.price_accessor = price_accessor
        self.min_profit_threshold = min_profit_threshold
        self.max_total_price_threshold = max_total_price_threshold
        self.price_type = price_type
        self.fee_rate_bps = fee_rate_bps
        self.slippage_bps = slippage_bps

    @staticmethod
    def _finite_float(value: Any, name: str) -> float:
        """Normalize scanner numeric inputs while rejecting NaN and infinities."""
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite")
        return normalized

    @staticmethod
    def require_buy_price_type(price_type: PriceType) -> None:
        """Fail closed when a buy-basket scanner is given a non-executable price."""
        if price_type != PriceType.ASK:
            raise ValueError(
                "Long-only basket scans require ASK prices; BID, MID, LIVE, and "
                "ACTUAL are not executable buy costs."
            )
    
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
        best_case_payoff: float,
        fee_rate_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate model-implied basket edge under explicit cost assumptions.
        
        Args:
            total_cost: Total cost of all legs
            worst_case_payoff: Conditional payoff assumed by the model
            best_case_payoff: Maximum possible payoff
            
        Returns:
            Dictionary using backward-compatible profit field names for model edge
        """
        total_cost = self._finite_float(total_cost, "total_cost")
        worst_case_payoff = self._finite_float(
            worst_case_payoff,
            "worst_case_payoff",
        )
        best_case_payoff = self._finite_float(best_case_payoff, "best_case_payoff")
        fee_rate_bps = self._finite_float(fee_rate_bps, "fee_rate_bps")
        slippage_bps = self._finite_float(slippage_bps, "slippage_bps")
        if (
            total_cost < 0
            or worst_case_payoff < 0
            or best_case_payoff < worst_case_payoff
        ):
            raise ValueError("Cost and payoff inputs violate scanner invariants")
        if fee_rate_bps < 0 or slippage_bps < 0:
            raise ValueError("Fee and slippage inputs must be non-negative")

        fee_cost = self._finite_float(
            total_cost * fee_rate_bps / 10000,
            "fee_cost",
        )
        slippage_cost = self._finite_float(
            total_cost * slippage_bps / 10000,
            "slippage_cost",
        )
        effective_cost = self._finite_float(
            total_cost + fee_cost + slippage_cost,
            "effective_cost",
        )
        expected_profit = self._finite_float(
            worst_case_payoff - effective_cost,
            "expected_profit",
        )
        profit_percentage = (
            self._finite_float(
                expected_profit / effective_cost * 100,
                "profit_percentage",
            )
            if effective_cost > 0
            else 0
        )
        
        return {
            "total_cost": total_cost,
            "worst_case_payoff": worst_case_payoff,
            "best_case_payoff": best_case_payoff,
            "fee_cost": fee_cost,
            "slippage_cost": slippage_cost,
            "effective_cost": effective_cost,
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
        total_cost = self._finite_float(total_cost, "total_cost")
        spread_multiplier = self._finite_float(
            spread_multiplier,
            "spread_multiplier",
        )
        spread_adjustment = 0.0
        
        for leg in legs:
            leg_price = self._finite_float(leg.price, "leg price")
            if hasattr(leg, "spread_bps") and leg.spread_bps is not None:
                spread_bps = self._finite_float(leg.spread_bps, "leg spread_bps")
                # Spread impact as percentage
                spread_impact = self._finite_float(
                    spread_bps / 10000 * leg_price,
                    "spread impact",
                )
                spread_adjustment = self._finite_float(
                    spread_adjustment + spread_impact * spread_multiplier,
                    "spread adjustment",
                )
        
        return self._finite_float(total_cost + spread_adjustment, "adjusted cost")
    
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
            if hasattr(leg, "depth") and leg.depth is not None:
                depths.append(self._finite_float(leg.depth, "leg depth"))
        
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
            profit_percentage: Backward-compatible model-edge percentage
            total_cost: Total cost
            
        Returns:
            True if valid
        """
        try:
            profit_percentage = self._finite_float(
                profit_percentage,
                "profit_percentage",
            )
            total_cost = self._finite_float(total_cost, "total_cost")
            threshold = self._finite_float(
                self.min_profit_threshold,
                "min_profit_threshold",
            )
        except ValueError:
            return False

        # Must meet the backward-compatible model-edge threshold.
        if profit_percentage < threshold:
            return False
        
        # Cost must be positive and reasonable
        if total_cost <= 0 or total_cost > 10:  # Max 10 per share
            return False
        
        return True

    @staticmethod
    def get_max_size(legs: List[Any]) -> Optional[float]:
        """Return the limiting displayed ask depth, including an explicit zero."""
        depths = [
            BaseScanner._finite_float(leg.depth, "leg depth")
            for leg in legs
            if getattr(leg, "depth", None) is not None
        ]
        return min(depths) if depths else None
