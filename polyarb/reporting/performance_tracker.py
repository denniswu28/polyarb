"""
Performance tracking and metrics calculation.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, OpportunityClass
from polyarb.execution.basket_executor import ExecutionResult
from polyarb.data.models import PriceType


@dataclass
class PerformanceMetrics:
    """Performance metrics for a set of opportunities or executions."""
    
    # Counts
    total_opportunities: int = 0
    executed_opportunities: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    
    # Financial metrics
    total_theoretical_profit: float = 0.0
    total_realized_profit: float = 0.0
    total_cost: float = 0.0
    total_slippage: float = 0.0
    
    # Performance metrics
    avg_profit_percentage: float = 0.0
    avg_slippage_bps: float = 0.0
    hit_rate: float = 0.0  # % of opportunities that remained profitable after execution
    
    # Breakdown by category
    by_opportunity_class: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_topic: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_price_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Time range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PerformanceTracker:
    """
    Tracks performance of arbitrage opportunities and executions.
    """
    
    def __init__(self):
        """Initialize performance tracker."""
        self.opportunities: List[EnhancedOpportunity] = []
        self.executions: Dict[str, ExecutionResult] = {}  # opp_id -> execution
        
        # Aggregated metrics
        self._metrics_cache: Optional[PerformanceMetrics] = None
        self._cache_dirty = True
    
    def add_opportunity(self, opportunity: EnhancedOpportunity) -> None:
        """
        Add discovered opportunity.
        
        Args:
            opportunity: Opportunity to track
        """
        self.opportunities.append(opportunity)
        self._cache_dirty = True
    
    def add_execution(
        self,
        opportunity_id: str,
        execution: ExecutionResult
    ) -> None:
        """
        Add execution result.
        
        Args:
            opportunity_id: ID of executed opportunity
            execution: Execution result
        """
        self.executions[opportunity_id] = execution
        self._cache_dirty = True
    
    def calculate_metrics(self, recalculate: bool = False) -> PerformanceMetrics:
        """
        Calculate performance metrics.
        
        Args:
            recalculate: Force recalculation even if cached
            
        Returns:
            PerformanceMetrics
        """
        if not self._cache_dirty and self._metrics_cache and not recalculate:
            return self._metrics_cache
        
        metrics = PerformanceMetrics()
        
        # Basic counts
        metrics.total_opportunities = len(self.opportunities)
        metrics.executed_opportunities = len(self.executions)
        
        # Financial metrics
        for opp in self.opportunities:
            metrics.total_theoretical_profit += opp.expected_profit
            metrics.total_cost += opp.total_cost
        
        # Execution metrics
        successful = 0
        failed = 0
        total_slippage = 0.0
        total_realized_profit = 0.0
        
        for opp_id, execution in self.executions.items():
            if execution.is_complete():
                successful += 1
                
                # Calculate realized profit
                # Find original opportunity
                opp = next((o for o in self.opportunities if o.id == opp_id), None)
                if opp:
                    realized_profit = opp.worst_case_payoff - execution.actual_cost
                    total_realized_profit += realized_profit
                
                total_slippage += execution.realized_slippage
            else:
                failed += 1
        
        metrics.successful_executions = successful
        metrics.failed_executions = failed
        metrics.total_realized_profit = total_realized_profit
        metrics.total_slippage = total_slippage
        
        # Averages
        if metrics.total_opportunities > 0:
            metrics.avg_profit_percentage = sum(
                o.profit_percentage for o in self.opportunities
            ) / metrics.total_opportunities
        
        if successful > 0:
            metrics.avg_slippage_bps = total_slippage / successful
            metrics.hit_rate = successful / metrics.executed_opportunities if metrics.executed_opportunities > 0 else 0
        
        # Breakdown by opportunity class
        class_metrics = defaultdict(lambda: {
            "count": 0, 
            "total_profit": 0.0, 
            "avg_profit_pct": 0.0
        })
        
        for opp in self.opportunities:
            key = opp.opportunity_class.value
            class_metrics[key]["count"] += 1
            class_metrics[key]["total_profit"] += opp.expected_profit
        
        for key, data in class_metrics.items():
            if data["count"] > 0:
                data["avg_profit_pct"] = data["total_profit"] / data["count"]
        
        metrics.by_opportunity_class = dict(class_metrics)
        
        # Breakdown by topic
        topic_metrics = defaultdict(lambda: {
            "count": 0,
            "total_profit": 0.0,
            "avg_profit_pct": 0.0
        })
        
        for opp in self.opportunities:
            if opp.topic:
                topic_metrics[opp.topic]["count"] += 1
                topic_metrics[opp.topic]["total_profit"] += opp.expected_profit
        
        for topic, data in topic_metrics.items():
            if data["count"] > 0:
                data["avg_profit_pct"] = data["total_profit"] / data["count"]
        
        metrics.by_topic = dict(topic_metrics)
        
        # Time range
        if self.opportunities:
            metrics.start_date = min(o.discovered_at for o in self.opportunities)
            metrics.end_date = max(o.discovered_at for o in self.opportunities)
        
        # Cache and return
        self._metrics_cache = metrics
        self._cache_dirty = False
        
        return metrics
    
    def get_top_opportunities(
        self,
        n: int = 10,
        by: str = "profit_percentage"
    ) -> List[EnhancedOpportunity]:
        """
        Get top N opportunities.
        
        Args:
            n: Number of opportunities to return
            by: Metric to sort by ('profit_percentage', 'expected_profit', etc.)
            
        Returns:
            List of top opportunities
        """
        return sorted(
            self.opportunities,
            key=lambda o: getattr(o, by, 0),
            reverse=True
        )[:n]
    
    def filter_opportunities(
        self,
        opportunity_class: Optional[OpportunityClass] = None,
        topic: Optional[str] = None,
        min_profit: Optional[float] = None
    ) -> List[EnhancedOpportunity]:
        """
        Filter opportunities by criteria.
        
        Args:
            opportunity_class: Filter by class
            topic: Filter by topic
            min_profit: Minimum profit percentage
            
        Returns:
            Filtered list of opportunities
        """
        filtered = self.opportunities
        
        if opportunity_class:
            filtered = [o for o in filtered if o.opportunity_class == opportunity_class]
        
        if topic:
            filtered = [o for o in filtered if o.topic == topic]
        
        if min_profit is not None:
            filtered = [o for o in filtered if o.profit_percentage >= min_profit]
        
        return filtered
    
    def clear(self) -> None:
        """Clear all tracked data."""
        self.opportunities.clear()
        self.executions.clear()
        self._metrics_cache = None
        self._cache_dirty = True
