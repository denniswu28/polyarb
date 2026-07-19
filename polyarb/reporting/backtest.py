"""
Historical backtesting API placeholder.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from polyarb.reporting.performance_tracker import PerformanceMetrics


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    
    start_date: datetime
    end_date: datetime
    
    total_opportunities: int = 0
    total_profit: float = 0.0
    total_trades: int = 0
    
    metrics: Optional[PerformanceMetrics] = None
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Render the compatibility result schema without implying validation."""
        average_edge = (
            f"{self.metrics.avg_profit_percentage:.2f}%" if self.metrics else "N/A"
        )
        settled_rate = f"{self.metrics.hit_rate:.1%}" if self.metrics else "N/A"
        return f"""
Backtest Result Schema (historical replay is not implemented)
=============================================================
Period: {self.start_date.date()} to {self.end_date.date()}
Total Opportunities: {self.total_opportunities}
Total Trades: {self.total_trades}
Model-Implied Edge: ${self.total_profit:.2f}

Average Model Edge %: {average_edge}
Positive Settled-Result Rate: {settled_rate}
"""


class Backtester:
    """
    Fail-closed placeholder retained for API compatibility.

    Historical replay is not implemented or validated. In particular, the
    repository has no historical order-book dataset, fill model, or settlement
    model that could support backtest or performance claims.
    """
    
    def __init__(
        self,
        min_profit_threshold: float = 0.5,
        max_total_price_threshold: float = 0.98
    ):
        """
        Initialize backtester.
        
        Args:
            min_profit_threshold: Legacy model-edge threshold field
            max_total_price_threshold: Legacy conditional basket-cost threshold
        """
        self.min_profit_threshold = min_profit_threshold
        self.max_total_price_threshold = max_total_price_threshold
    
    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        markets_data: List[Dict[str, Any]],
        **kwargs
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            markets_data: Historical market data
            **kwargs: Additional parameters
            
        Returns:
            BacktestResult
        """
        del start_date, end_date, markets_data, kwargs
        raise NotImplementedError(
            "Historical backtesting is not implemented or validated in polyarb."
        )
    
    def _is_in_date_range(
        self,
        market: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> bool:
        """Check if market data is within date range."""
        timestamp = market.get("timestamp")
        if not timestamp:
            return False
        
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        return start_date <= timestamp <= end_date
    
    def _simulate_opportunity_from_snapshot(
        self,
        market_snapshot: Dict[str, Any]
    ) -> None:
        """
        Simulate opportunity discovery from historical snapshot.
        
        Any future implementation would need to:
        1. Reconstruct orderbook state
        2. Calculate prices
        3. Run scanner logic
        4. Return discovered opportunity
        
        Args:
            market_snapshot: Historical market snapshot
            
        Returns:
            EnhancedOpportunity or None
        """
        del market_snapshot
        raise NotImplementedError(
            "Historical snapshot replay is not implemented or validated in polyarb."
        )
    
    def compare_price_types(
        self,
        markets_data: List[Dict[str, Any]],
        price_types: List[str]
    ) -> Dict[str, BacktestResult]:
        """
        Placeholder for a historical price-type comparison.
        
        Args:
            markets_data: Historical market data
            price_types: List of price types to compare
            
        Returns:
            Dictionary mapping price_type to BacktestResult
        """
        del markets_data, price_types
        raise NotImplementedError(
            "Historical price-type comparison is not implemented or validated in polyarb."
        )
