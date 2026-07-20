"""Deterministic simulated basket execution with live submission disabled."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import TYPE_CHECKING, List, Optional, Sequence

from polyarb.core.lifecycle import LifecycleState
from polyarb.scanner.enhanced_opportunity import EnhancedOpportunity, Leg

if TYPE_CHECKING:
    from polyarb.execution.risk_manager import RiskManager


def _finite_float(value: object, name: str) -> float:
    """Normalize a numeric simulation input and reject NaN and infinities."""
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


class ExecutionMode(str, Enum):
    """Execution modes exposed by the framework."""

    SIMULATED = "simulated"
    LIVE = "live"


class ExecutionStatus(str, Enum):
    """Execution and fill statuses; these states are intentionally distinct."""

    PENDING = "pending"
    SIMULATED = "simulated"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    SETTLED = "settled"
    REPORTED = "reported"
    FAILED = "failed"

    # Backward-compatible legacy members. New code should use the explicit states above.
    PARTIAL = "partial"
    COMPLETED = "completed"
    ABORTED = "aborted"


class LiveExecutionDisabledError(RuntimeError):
    """Raised before any live-order path can submit an order."""


class OpportunityNotApprovedError(RuntimeError):
    """Raised when simulation is requested before an opportunity is approved."""


@dataclass
class LegExecution:
    """Fill result for one leg; simulated fills never contain an order ID."""

    leg: Leg
    status: ExecutionStatus
    requested_size: float = 0.0
    filled_size: float = 0.0
    avg_fill_price: Optional[float] = None
    slippage_bps: Optional[float] = None
    order_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    is_simulated: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExecutionResult:
    """Basket result with simulation, fill, settlement, and report states separated."""

    opportunity_id: str
    status: ExecutionStatus
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED
    lifecycle_state: LifecycleState = LifecycleState.SIMULATED
    fill_status: Optional[ExecutionStatus] = None
    leg_executions: List[LegExecution] = field(default_factory=list)

    total_cost: float = 0.0
    simulated_cost: float = 0.0
    simulated_slippage_bps: float = 0.0
    actual_cost: float = 0.0
    realized_slippage: float = 0.0
    settled_payout: Optional[float] = None

    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    reported_at: Optional[datetime] = None
    notes: List[str] = field(default_factory=list)

    def get_fill_rate(self) -> float:
        """Return filled size divided by requested size across all simulated legs."""
        requested = _finite_float(
            sum(
                _finite_float(leg.requested_size, "leg requested_size")
                for leg in self.leg_executions
            ),
            "aggregate requested size",
        )
        if requested <= 0:
            return 0.0
        filled = _finite_float(
            sum(
                _finite_float(leg.filled_size, "leg filled_size")
                for leg in self.leg_executions
            ),
            "aggregate filled size",
        )
        return _finite_float(filled / requested, "fill rate")

    def is_simulated(self) -> bool:
        """Return whether this record describes a simulation."""
        return self.lifecycle_state == LifecycleState.SIMULATED

    def is_filled(self) -> bool:
        """Return whether a real submitted basket is recorded as fully filled."""
        return (
            self.execution_mode == ExecutionMode.LIVE
            and self.lifecycle_state in {LifecycleState.FILLED, LifecycleState.SETTLED}
        )

    def is_settled(self) -> bool:
        """Return whether a real fill has a recorded settlement."""
        return (
            self.execution_mode == ExecutionMode.LIVE
            and self.lifecycle_state == LifecycleState.SETTLED
        )

    def is_complete(self) -> bool:
        """Backward-compatible alias for a real filled or settled result."""
        return self.is_filled()

    def get_failed_legs(self) -> List[LegExecution]:
        """Return failed or cancelled legs."""
        return [
            leg
            for leg in self.leg_executions
            if leg.status in {ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}
        ]

    def mark_reported(self) -> None:
        """Record reporting without changing fill or settlement evidence."""
        self.reported_at = datetime.utcnow()


class BasketExecutor:
    """Run deterministic paper simulations; live order submission is unavailable."""

    def __init__(
        self,
        max_slippage_bps: float = 50,
        min_fill_rate: float = 0.8,
        execution_timeout: int = 60,
        execution_mode: ExecutionMode = ExecutionMode.SIMULATED,
        risk_manager: Optional["RiskManager"] = None,
    ):
        max_slippage_bps = _finite_float(max_slippage_bps, "max_slippage_bps")
        min_fill_rate = _finite_float(min_fill_rate, "min_fill_rate")
        execution_timeout = _finite_float(execution_timeout, "execution_timeout")
        if max_slippage_bps < 0:
            raise ValueError("max_slippage_bps must be non-negative")
        if not 0 <= min_fill_rate <= 1:
            raise ValueError("min_fill_rate must be between 0 and 1")
        if execution_timeout <= 0:
            raise ValueError("execution_timeout must be positive")

        self.max_slippage_bps = max_slippage_bps
        self.min_fill_rate = min_fill_rate
        self.execution_timeout = execution_timeout
        self.execution_mode = ExecutionMode(execution_mode)
        self.risk_manager = risk_manager

    async def execute_opportunity(
        self,
        opportunity: EnhancedOpportunity,
        target_size: float = 1.0,
        aggressive: bool = False,
        simulation_fill_ratios: Optional[Sequence[float]] = None,
        simulation_slippage_bps: Optional[Sequence[float]] = None,
    ) -> ExecutionResult:
        """Simulate an approved opportunity without creating or submitting orders."""
        if self.execution_mode != ExecutionMode.SIMULATED:
            raise LiveExecutionDisabledError(
                "Live order submission is disabled and not implemented in polyarb."
            )
        target_size = _finite_float(target_size, "target_size")
        self.max_slippage_bps = _finite_float(
            self.max_slippage_bps,
            "max_slippage_bps",
        )
        self.min_fill_rate = _finite_float(self.min_fill_rate, "min_fill_rate")
        self.execution_timeout = _finite_float(
            self.execution_timeout,
            "execution_timeout",
        )
        if self.max_slippage_bps < 0:
            raise ValueError("max_slippage_bps must be non-negative")
        if not 0 <= self.min_fill_rate <= 1:
            raise ValueError("min_fill_rate must be between 0 and 1")
        if self.execution_timeout <= 0:
            raise ValueError("execution_timeout must be positive")
        if self.risk_manager is None or not self.risk_manager.has_active_approval(
            opportunity,
            target_size,
        ):
            raise OpportunityNotApprovedError(
                "Simulated execution requires an active, unchanged RiskManager-issued "
                "approval reservation for this opportunity and exact size."
            )
        if target_size <= 0:
            raise ValueError("target_size must be positive")
        if opportunity.max_size is not None and target_size > opportunity.max_size:
            raise ValueError("target_size exceeds the opportunity liquidity constraint")

        fill_ratios = self._validated_inputs(
            simulation_fill_ratios,
            len(opportunity.legs),
            default=1.0,
            lower=0.0,
            upper=1.0,
            name="simulation_fill_ratios",
        )
        default_slippage = 10.0 if aggressive else 5.0
        slippage_values = self._validated_inputs(
            simulation_slippage_bps,
            len(opportunity.legs),
            default=default_slippage,
            lower=0.0,
            upper=None,
            name="simulation_slippage_bps",
        )

        modeled_total_cost = _finite_float(
            _finite_float(opportunity.total_cost, "opportunity total_cost")
            * target_size,
            "modeled total cost",
        )
        result = ExecutionResult(
            opportunity_id=opportunity.id,
            status=ExecutionStatus.SIMULATED,
            total_cost=modeled_total_cost,
            notes=["Paper simulation only; no order was created or submitted."],
        )

        for leg, fill_ratio, slippage_bps in zip(
            opportunity.legs, fill_ratios, slippage_values
        ):
            result.leg_executions.append(
                await self._execute_leg(
                    leg,
                    target_size,
                    aggressive,
                    opportunity,
                    fill_ratio=fill_ratio,
                    slippage_bps=slippage_bps,
                )
            )

        result.completed_at = datetime.utcnow()
        result.simulated_cost = _finite_float(
            sum(
                _finite_float(leg.avg_fill_price, "simulated fill price")
                * _finite_float(leg.filled_size, "simulated filled size")
                for leg in result.leg_executions
                if leg.avg_fill_price is not None
            ),
            "simulated cost",
        )
        expected_cost_of_filled_size = _finite_float(
            sum(
                _finite_float(leg.leg.price, "leg price")
                * _finite_float(leg.filled_size, "simulated filled size")
                for leg in result.leg_executions
            ),
            "expected cost of filled size",
        )
        if expected_cost_of_filled_size > 0:
            result.simulated_slippage_bps = _finite_float(
                (result.simulated_cost - expected_cost_of_filled_size)
                / expected_cost_of_filled_size
                * 10000,
                "simulated slippage",
            )

        fill_rate = result.get_fill_rate()
        if fill_rate == 1.0:
            result.fill_status = ExecutionStatus.FILLED
        elif fill_rate > 0:
            result.fill_status = ExecutionStatus.PARTIALLY_FILLED
        else:
            result.fill_status = ExecutionStatus.CANCELLED

        if fill_rate < self.min_fill_rate:
            result.notes.append(
                f"Simulated fill rate {fill_rate:.1%} is below the configured "
                f"minimum {self.min_fill_rate:.1%}."
            )
        return result

    async def submit_live_order(self, *args, **kwargs):
        """Fail closed before credentials, wallets, or network clients are consulted."""
        raise LiveExecutionDisabledError(
            "Live order submission is disabled and not implemented in polyarb."
        )

    async def _execute_leg(
        self,
        leg: Leg,
        size: float,
        aggressive: bool,
        opportunity: EnhancedOpportunity,
        fill_ratio: float = 1.0,
        slippage_bps: Optional[float] = None,
    ) -> LegExecution:
        """Create one deterministic simulated leg result."""
        del aggressive, opportunity
        size = _finite_float(size, "simulated leg size")
        fill_ratio = _finite_float(fill_ratio, "simulation fill ratio")
        if not 0 <= fill_ratio <= 1:
            raise ValueError("simulation fill ratio must be between 0 and 1")
        applied_slippage = _finite_float(
            5.0 if slippage_bps is None else slippage_bps,
            "simulation slippage",
        )
        if applied_slippage < 0:
            raise ValueError("simulation slippage must be non-negative")
        leg_price = _finite_float(leg.price, "leg price")
        risk_slippage_limit = (
            self.risk_manager.limits.max_slippage_tolerance
            if self.risk_manager is not None
            else self.max_slippage_bps
        )
        allowed_slippage = min(
            _finite_float(self.max_slippage_bps, "max_slippage_bps"),
            _finite_float(risk_slippage_limit, "risk slippage limit"),
        )
        if fill_ratio == 0 or applied_slippage > allowed_slippage:
            reason = (
                "simulated no-fill"
                if fill_ratio == 0
                else "simulated slippage exceeded configured limit"
            )
            return LegExecution(
                leg=leg,
                status=ExecutionStatus.CANCELLED,
                requested_size=size,
                slippage_bps=applied_slippage,
                error_message=reason,
            )

        filled_size = _finite_float(size * fill_ratio, "simulated filled size")
        actual_price = _finite_float(
            leg_price * (1 + applied_slippage / 10000),
            "simulated fill price",
        )
        status = (
            ExecutionStatus.FILLED
            if fill_ratio == 1.0
            else ExecutionStatus.PARTIALLY_FILLED
        )
        return LegExecution(
            leg=leg,
            status=status,
            requested_size=size,
            filled_size=filled_size,
            avg_fill_price=actual_price,
            slippage_bps=applied_slippage,
            order_ids=[],
        )

    @staticmethod
    def _validated_inputs(
        values: Optional[Sequence[float]],
        count: int,
        *,
        default: float,
        lower: float,
        upper: Optional[float],
        name: str,
    ) -> List[float]:
        if values is None:
            return [default] * count
        if len(values) != count:
            raise ValueError(f"{name} must contain one value per opportunity leg")
        normalized = [_finite_float(value, f"{name} value") for value in values]
        if any(value < lower or (upper is not None and value > upper) for value in normalized):
            bound = f"[{lower}, {upper}]" if upper is not None else f">= {lower}"
            raise ValueError(f"{name} values must be within {bound}")
        return normalized

    def _should_continue_after_failure(self, result: ExecutionResult) -> bool:
        """Retained for callers of the legacy helper; simulations evaluate every leg."""
        return result.get_fill_rate() >= self.min_fill_rate

    async def recompute_opportunity_edge(
        self,
        opportunity: EnhancedOpportunity,
        executed_legs: List[LegExecution],
    ) -> float:
        """Recompute the model-implied remaining edge after simulated fills."""
        executed_token_ids = {
            leg.leg.token_id
            for leg in executed_legs
            if _finite_float(leg.filled_size, "executed filled size") > 0
        }
        executed_cost = _finite_float(
            sum(
                _finite_float(leg.avg_fill_price, "executed fill price")
                * _finite_float(leg.filled_size, "executed filled size")
                for leg in executed_legs
                if leg.avg_fill_price is not None
            ),
            "executed cost",
        )
        remaining_cost = _finite_float(
            sum(
                _finite_float(leg.price, "remaining leg price")
                for leg in opportunity.legs
                if leg.token_id not in executed_token_ids
            ),
            "remaining cost",
        )
        total_cost = _finite_float(executed_cost + remaining_cost, "total cost")
        model_edge = _finite_float(
            _finite_float(opportunity.worst_case_payoff, "worst_case_payoff")
            - total_cost,
            "model edge",
        )
        return (
            _finite_float(model_edge / total_cost * 100, "model edge percentage")
            if total_cost > 0
            else 0.0
        )
