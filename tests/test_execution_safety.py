"""Offline tests for risk approval, simulations, partial fills, and reporting boundaries."""

import pytest

from polyarb.core.lifecycle import LifecycleState
from polyarb.execution import (
    BasketExecutor,
    ExecutionMode,
    ExecutionResult,
    ExecutionStatus,
    LiveExecutionDisabledError,
    OpportunityNotApprovedError,
    RiskLimits,
    RiskManager,
)
from polyarb.reporting import PerformanceTracker, UnvalidatedLiveExecutionError
from polyarb.scanner.enhanced_opportunity import (
    EnhancedOpportunity,
    Leg,
    OpportunityClass,
)


def make_opportunity(*, max_size=2.0, liquidity_score=0.8, opportunity_id="opp-1"):
    legs = [
        Leg("yes", "YES", "Yes", "market", "Synthetic?", 0.45, "ask", depth=10),
        Leg("no", "NO", "No", "market", "Synthetic?", 0.45, "ask", depth=10),
    ]
    return EnhancedOpportunity(
        id=opportunity_id,
        opportunity_class=OpportunityClass.SINGLE_CONDITION,
        name="Synthetic candidate",
        legs=legs,
        total_cost=0.90,
        worst_case_payoff=1.0,
        best_case_payoff=1.0,
        expected_profit=0.10,
        profit_percentage=11.111,
        max_size=max_size,
        liquidity_score=liquidity_score,
        market_ids=["market"],
    )


def test_risk_limits_reject_exposure_and_liquidity_constraints():
    opportunity = make_opportunity(max_size=0.5, liquidity_score=0.1)
    manager = RiskManager(
        RiskLimits(
            max_total_notional=0.5,
            min_liquidity_score=0.3,
        )
    )

    passed, violations = manager.check_opportunity(opportunity, proposed_size=1.0)

    assert passed is False
    assert any("liquidity-constrained" in violation for violation in violations)
    assert any("max total notional" in violation for violation in violations)
    assert any("Liquidity score" in violation for violation in violations)
    assert opportunity.lifecycle_state == LifecycleState.DETECTED


def test_risk_approval_reserves_notional_and_leg_capacity():
    opportunity = make_opportunity()
    manager = RiskManager()

    passed, violations = manager.approve_opportunity(opportunity, proposed_size=1.0)

    assert passed is True
    assert violations == []
    assert opportunity.lifecycle_state == LifecycleState.APPROVED
    assert opportunity.approved_at is not None
    summary = manager.get_exposure_summary()
    assert summary["total_notional"] == pytest.approx(0.90)
    assert summary["approved_notional"] == pytest.approx(0.90)
    assert summary["approved_positions"] == 2
    assert summary["total_positions"] == 2


def test_two_leg_approval_cannot_exceed_aggregate_position_cap():
    opportunity = make_opportunity()
    manager = RiskManager(RiskLimits(max_positions=1))

    passed, violations = manager.approve_opportunity(opportunity, proposed_size=1.0)

    assert passed is False
    assert any("max positions limit" in violation for violation in violations)
    assert manager.get_exposure_summary()["total_notional"] == 0.0


def test_repeated_approvals_cannot_exceed_aggregate_notional():
    first = make_opportunity(opportunity_id="opp-1")
    second = make_opportunity(opportunity_id="opp-2")
    manager = RiskManager(RiskLimits(max_total_notional=1.5))

    assert manager.approve_opportunity(first, proposed_size=1.0) == (True, [])
    passed, violations = manager.approve_opportunity(second, proposed_size=1.0)

    assert passed is False
    assert any("max total notional" in violation for violation in violations)
    assert manager.get_exposure_summary()["total_notional"] == pytest.approx(0.90)


def test_zero_liquidity_produces_zero_suggested_size():
    opportunity = make_opportunity(max_size=0.0)
    manager = RiskManager()

    assert manager.suggest_position_size(opportunity) == 0.0
    assert manager.suggest_position_size(opportunity, max_size=0.0) == 0.0


@pytest.mark.asyncio
async def test_simulation_requires_approval_and_records_partial_fill_without_order_ids():
    opportunity = make_opportunity()
    executor = BasketExecutor(max_slippage_bps=50, min_fill_rate=0.8)

    with pytest.raises(OpportunityNotApprovedError):
        await executor.execute_opportunity(opportunity)

    opportunity.approve()
    result = await executor.execute_opportunity(
        opportunity,
        simulation_fill_ratios=[1.0, 0.5],
        simulation_slippage_bps=[5.0, 10.0],
    )

    assert result.status == ExecutionStatus.SIMULATED
    assert result.lifecycle_state == LifecycleState.SIMULATED
    assert result.fill_status == ExecutionStatus.PARTIALLY_FILLED
    assert result.get_fill_rate() == pytest.approx(0.75)
    assert result.actual_cost == 0.0
    assert result.simulated_cost > 0
    assert all(leg.order_ids == [] for leg in result.leg_executions)
    assert result.is_complete() is False


@pytest.mark.asyncio
async def test_simulated_slippage_limit_cancels_leg():
    opportunity = make_opportunity()
    opportunity.approve()
    executor = BasketExecutor(max_slippage_bps=20)

    result = await executor.execute_opportunity(
        opportunity,
        simulation_slippage_bps=[5.0, 25.0],
    )

    assert result.fill_status == ExecutionStatus.PARTIALLY_FILLED
    assert result.leg_executions[1].status == ExecutionStatus.CANCELLED
    assert result.get_fill_rate() == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_live_order_paths_fail_closed():
    opportunity = make_opportunity()
    opportunity.approve()
    executor = BasketExecutor(execution_mode=ExecutionMode.LIVE)

    with pytest.raises(LiveExecutionDisabledError, match="disabled"):
        await executor.execute_opportunity(opportunity)
    with pytest.raises(LiveExecutionDisabledError, match="disabled"):
        await executor.submit_live_order(opportunity)


@pytest.mark.asyncio
async def test_simulation_is_excluded_from_execution_and_realized_metrics():
    opportunity = make_opportunity()
    opportunity.approve()
    result = await BasketExecutor().execute_opportunity(opportunity)
    tracker = PerformanceTracker()
    tracker.add_opportunity(opportunity)
    tracker.add_execution(opportunity.id, result)

    metrics = tracker.calculate_metrics()

    assert metrics.simulated_executions == 1
    assert metrics.submitted_executions == 0
    assert metrics.executed_opportunities == 0
    assert metrics.filled_executions == 0
    assert metrics.settled_executions == 0
    assert metrics.total_realized_profit == 0.0
    assert metrics.hit_rate == 0.0


def test_direct_live_settlement_record_is_rejected_without_validated_importer():
    opportunity = make_opportunity()
    tracker = PerformanceTracker()
    tracker.add_opportunity(opportunity)
    settlement = ExecutionResult(
        opportunity_id=opportunity.id,
        status=ExecutionStatus.SETTLED,
        execution_mode=ExecutionMode.LIVE,
        lifecycle_state=LifecycleState.SETTLED,
        actual_cost=0.90,
        settled_payout=1.0,
    )
    with pytest.raises(UnvalidatedLiveExecutionError, match="no provenance-bearing"):
        tracker.add_execution(opportunity.id, settlement)

    metrics = tracker.calculate_metrics()
    assert metrics.submitted_executions == 0
    assert metrics.settled_executions == 0
    assert metrics.total_realized_profit == 0.0
    assert metrics.hit_rate == 0.0


@pytest.mark.asyncio
async def test_mutating_stored_simulation_to_live_evidence_fails_closed():
    opportunity = make_opportunity()
    opportunity.approve()
    result = await BasketExecutor().execute_opportunity(opportunity)
    tracker = PerformanceTracker()
    tracker.add_execution(opportunity.id, result)
    tracker.calculate_metrics()

    result.execution_mode = ExecutionMode.LIVE
    result.lifecycle_state = LifecycleState.SETTLED
    result.settled_payout = 1.0

    with pytest.raises(UnvalidatedLiveExecutionError, match="no provenance-bearing"):
        tracker.calculate_metrics()
