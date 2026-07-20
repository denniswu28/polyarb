"""Backward-compatible tracking for research lifecycle and model fields."""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, OpportunityClass
from polyarb.core.lifecycle import LifecycleState
from polyarb.execution.basket_executor import ExecutionMode, ExecutionResult, ExecutionStatus


class UnvalidatedLiveExecutionError(RuntimeError):
    """Raised when unvalidated live/fill/settlement evidence reaches reporting."""


@dataclass
class PerformanceMetrics:
    """Research counters with modeled edge separated from settled outcomes."""
    
    # Counts
    total_opportunities: int = 0
    executed_opportunities: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    detected_opportunities: int = 0
    approved_opportunities: int = 0
    simulated_executions: int = 0
    submitted_executions: int = 0
    filled_executions: int = 0
    partially_filled_executions: int = 0
    cancelled_executions: int = 0
    settled_executions: int = 0
    reported_records: int = 0
    
    # Financial metrics
    total_theoretical_profit: float = 0.0  # Backward-compatible model-implied edge
    total_model_implied_edge: float = 0.0
    total_realized_profit: float = 0.0  # Unsupported until a validated importer exists
    total_cost: float = 0.0
    total_slippage: float = 0.0
    
    # Backward-compatible research/settlement fields
    avg_profit_percentage: float = 0.0
    avg_slippage_bps: float = 0.0
    hit_rate: float = 0.0  # Unsupported until a validated importer exists
    
    # Breakdown by category
    by_opportunity_class: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_topic: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_price_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Time range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PerformanceTracker:
    """
    Tracks research records without treating simulations as live execution.
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
        if execution.opportunity_id != opportunity_id:
            raise ValueError("Execution result does not match opportunity_id")
        self._validate_execution_record(execution)
        self.executions[opportunity_id] = execution
        self._cache_dirty = True

    @staticmethod
    def _validate_execution_record(execution: ExecutionResult) -> None:
        """Allow only simulation evidence until a validated importer exists."""
        simulated_fill_states = {
            None,
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
            ExecutionStatus.CANCELLED,
        }
        if (
            execution.execution_mode != ExecutionMode.SIMULATED
            or execution.lifecycle_state != LifecycleState.SIMULATED
            or execution.status != ExecutionStatus.SIMULATED
            or execution.fill_status not in simulated_fill_states
            or execution.actual_cost != 0
            or execution.realized_slippage != 0
            or execution.settled_payout is not None
            or any(
                not leg.is_simulated
                or leg.order_ids
                or leg.status not in simulated_fill_states
                for leg in execution.leg_executions
            )
        ):
            raise UnvalidatedLiveExecutionError(
                "Live, submitted, filled, cancelled, and settled records are rejected: "
                "polyarb has no provenance-bearing validated execution/settlement importer."
            )
    
    def calculate_metrics(self, recalculate: bool = False) -> PerformanceMetrics:
        """
        Calculate bounded research and simulation metrics.
        
        Args:
            recalculate: Force recalculation even if cached
            
        Returns:
            PerformanceMetrics
        """
        for execution in self.executions.values():
            self._validate_execution_record(execution)
        if not self._cache_dirty and self._metrics_cache and not recalculate:
            return self._metrics_cache
        
        metrics = PerformanceMetrics()
        
        # Basic counts
        metrics.total_opportunities = len(self.opportunities)
        metrics.detected_opportunities = sum(
            1
            for opportunity in self.opportunities
            if opportunity.lifecycle_state == LifecycleState.DETECTED
        )
        metrics.approved_opportunities = sum(
            1
            for opportunity in self.opportunities
            if opportunity.lifecycle_state == LifecycleState.APPROVED
        )
        
        # Financial metrics
        for opp in self.opportunities:
            metrics.total_theoretical_profit += opp.expected_profit
            metrics.total_model_implied_edge += opp.expected_profit
            metrics.total_cost += opp.total_cost
            if opp.reported_at is not None:
                metrics.reported_records += 1
        
        # Execution metrics. Revalidate mutable records on every calculation so a
        # caller cannot mutate a stored simulation into fabricated live evidence.
        for execution in self.executions.values():
            metrics.simulated_executions += 1
            if execution.fill_status == ExecutionStatus.PARTIALLY_FILLED:
                metrics.partially_filled_executions += 1
            elif execution.fill_status == ExecutionStatus.CANCELLED:
                metrics.cancelled_executions += 1
            if execution.reported_at is not None:
                metrics.reported_records += 1

        metrics.executed_opportunities = metrics.submitted_executions
        
        # Averages
        if metrics.total_opportunities > 0:
            metrics.avg_profit_percentage = sum(
                o.profit_percentage for o in self.opportunities
            ) / metrics.total_opportunities
        
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
            class_metrics[key].setdefault("profit_pct_sum", 0.0)
            class_metrics[key]["profit_pct_sum"] += opp.profit_percentage
        
        for key, data in class_metrics.items():
            if data["count"] > 0:
                data["avg_profit_pct"] = data["profit_pct_sum"] / data["count"]
                del data["profit_pct_sum"]
        
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
                topic_metrics[opp.topic].setdefault("profit_pct_sum", 0.0)
                topic_metrics[opp.topic]["profit_pct_sum"] += opp.profit_percentage
        
        for topic, data in topic_metrics.items():
            if data["count"] > 0:
                data["avg_profit_pct"] = data["profit_pct_sum"] / data["count"]
                del data["profit_pct_sum"]
        
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
            min_profit: Minimum model-edge percentage
            
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
