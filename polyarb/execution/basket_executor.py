"""
Basket execution for multi-leg arbitrage opportunities.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from decimal import Decimal

from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, Leg
from polyarb.data.models import Trade


class ExecutionStatus(str, Enum):
    """Status of execution."""
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class LegExecution:
    """Execution result for a single leg."""
    
    leg: Leg
    status: ExecutionStatus
    filled_size: float = 0.0
    avg_fill_price: Optional[float] = None
    slippage_bps: Optional[float] = None
    order_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExecutionResult:
    """Result of basket execution."""
    
    opportunity_id: str
    status: ExecutionStatus
    leg_executions: List[LegExecution] = field(default_factory=list)
    
    total_cost: float = 0.0
    actual_cost: float = 0.0
    realized_slippage: float = 0.0
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    notes: List[str] = field(default_factory=list)
    
    def get_fill_rate(self) -> float:
        """Get overall fill rate (0-1)."""
        if not self.leg_executions:
            return 0.0
        
        filled = sum(1 for le in self.leg_executions if le.status == ExecutionStatus.COMPLETED)
        return filled / len(self.leg_executions)
    
    def is_complete(self) -> bool:
        """Check if all legs are filled."""
        return self.status == ExecutionStatus.COMPLETED
    
    def get_failed_legs(self) -> List[LegExecution]:
        """Get legs that failed to execute."""
        return [le for le in self.leg_executions if le.status == ExecutionStatus.FAILED]


class BasketExecutor:
    """
    Executes multi-leg arbitrage baskets with non-atomic fill handling.
    
    Note: This is a framework class. In production, you would integrate
    with actual trading APIs (Polymarket CLOB, order placement, etc.).
    """
    
    def __init__(
        self,
        max_slippage_bps: float = 50,  # 0.5%
        min_fill_rate: float = 0.8,  # 80% of legs must fill
        execution_timeout: int = 60,  # seconds
    ):
        """
        Initialize basket executor.
        
        Args:
            max_slippage_bps: Maximum acceptable slippage in basis points
            min_fill_rate: Minimum fill rate to consider execution successful
            execution_timeout: Timeout for execution in seconds
        """
        self.max_slippage_bps = max_slippage_bps
        self.min_fill_rate = min_fill_rate
        self.execution_timeout = execution_timeout
    
    async def execute_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        target_size: float = 1.0,
        aggressive: bool = False
    ) -> ExecutionResult:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            target_size: Target notional size per leg
            aggressive: Whether to cross the spread aggressively
            
        Returns:
            ExecutionResult
        """
        result = ExecutionResult(
            opportunity_id=opportunity.id,
            status=ExecutionStatus.PENDING,
            total_cost=opportunity.total_cost * target_size
        )
        
        # Execute each leg
        for leg in opportunity.legs:
            leg_result = await self._execute_leg(
                leg, 
                target_size,
                aggressive,
                opportunity
            )
            result.leg_executions.append(leg_result)
            
            # Check if we should abort
            if leg_result.status == ExecutionStatus.FAILED:
                if not self._should_continue_after_failure(result):
                    result.status = ExecutionStatus.ABORTED
                    result.notes.append(f"Aborted after leg {leg.outcome_label} failed")
                    break
        
        # Finalize result
        result.completed_at = datetime.utcnow()
        
        # Calculate actual metrics
        result.actual_cost = sum(
            le.avg_fill_price * le.filled_size 
            for le in result.leg_executions 
            if le.avg_fill_price
        )
        
        if result.total_cost > 0:
            result.realized_slippage = ((result.actual_cost - result.total_cost) / 
                                       result.total_cost * 10000)
        
        # Determine final status
        fill_rate = result.get_fill_rate()
        if fill_rate >= self.min_fill_rate:
            result.status = ExecutionStatus.COMPLETED
        elif fill_rate > 0:
            result.status = ExecutionStatus.PARTIAL
        else:
            result.status = ExecutionStatus.FAILED
        
        return result
    
    async def _execute_leg(
        self,
        leg: Leg,
        size: float,
        aggressive: bool,
        opportunity: EnhancedOpportunity
    ) -> LegExecution:
        """
        Execute a single leg.
        
        This is a placeholder for actual order execution logic.
        
        Args:
            leg: Leg to execute
            size: Size to execute
            aggressive: Whether to cross spread
            opportunity: Parent opportunity
            
        Returns:
            LegExecution
        """
        leg_exec = LegExecution(
            leg=leg,
            status=ExecutionStatus.PENDING
        )
        
        try:
            # In production, this would:
            # 1. Place limit or market order via CLOB API
            # 2. Monitor fills
            # 3. Handle partial fills
            # 4. Calculate slippage
            
            # Placeholder: simulate execution
            # Assume successful fill at expected price + slippage
            expected_price = leg.price
            slippage_factor = 0.001 if aggressive else 0.0005  # 0.1% or 0.05%
            actual_price = expected_price * (1 + slippage_factor)
            
            leg_exec.status = ExecutionStatus.COMPLETED
            leg_exec.filled_size = size
            leg_exec.avg_fill_price = actual_price
            leg_exec.slippage_bps = (actual_price - expected_price) / expected_price * 10000
            leg_exec.order_ids = ["simulated_order_id"]
            
        except Exception as e:
            leg_exec.status = ExecutionStatus.FAILED
            leg_exec.error_message = str(e)
        
        return leg_exec
    
    def _should_continue_after_failure(self, result: ExecutionResult) -> bool:
        """
        Decide whether to continue execution after a leg failure.
        
        Args:
            result: Current execution result
            
        Returns:
            True if should continue
        """
        # Check current fill rate
        if len(result.leg_executions) == 0:
            return True
        
        filled = sum(1 for le in result.leg_executions if le.status == ExecutionStatus.COMPLETED)
        total = len(result.leg_executions)
        
        # If we're below min fill rate and have few legs left, abort
        if filled / (total + 1) < self.min_fill_rate:
            return False
        
        return True
    
    async def recompute_opportunity_edge(
        self,
        opportunity: EnhancedOpportunity,
        executed_legs: List[LegExecution]
    ) -> float:
        """
        Recompute remaining edge after partial fills.
        
        Args:
            opportunity: Original opportunity
            executed_legs: Legs that have been executed
            
        Returns:
            Remaining profit percentage
        """
        executed_token_ids = {le.leg.token_id for le in executed_legs}
        
        # Cost of executed legs
        executed_cost = sum(
            le.avg_fill_price * le.filled_size 
            for le in executed_legs 
            if le.avg_fill_price
        )
        
        # Estimated cost of remaining legs
        remaining_cost = sum(
            leg.price 
            for leg in opportunity.legs 
            if leg.token_id not in executed_token_ids
        )
        
        total_cost = executed_cost + remaining_cost
        
        # Recalculate edge
        expected_payoff = opportunity.worst_case_payoff
        profit = expected_payoff - total_cost
        profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
        
        return profit_pct
