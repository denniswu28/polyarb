"""Offline tests for risk approval, simulations, partial fills, and reporting boundaries."""

from datetime import datetime, timedelta, timezone

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
    RiskLevel,
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


def approve_for_simulation(opportunity, *, limits=None, size=1.0):
    manager = RiskManager(limits)
    assert manager.approve_opportunity(opportunity, proposed_size=size) == (True, [])
    return manager


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
    manager = RiskManager()
    executor = BasketExecutor(
        max_slippage_bps=50,
        min_fill_rate=0.8,
        risk_manager=manager,
    )

    with pytest.raises(OpportunityNotApprovedError):
        await executor.execute_opportunity(opportunity)

    assert manager.approve_opportunity(opportunity, proposed_size=1.0) == (True, [])
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
async def test_direct_approval_cannot_bypass_risk_manager_limits():
    opportunity = make_opportunity()
    opportunity.approve()
    manager = RiskManager(RiskLimits(max_total_notional=0.0, max_positions=0))
    executor = BasketExecutor(risk_manager=manager)

    with pytest.raises(OpportunityNotApprovedError, match="RiskManager-issued"):
        await executor.execute_opportunity(opportunity)


@pytest.mark.asyncio
async def test_released_approval_cannot_be_executed():
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    executor = BasketExecutor(risk_manager=manager)

    manager.release_approval(opportunity.id)

    assert opportunity.lifecycle_state == LifecycleState.DETECTED
    assert manager.get_exposure_summary()["approved_notional"] == 0.0
    with pytest.raises(OpportunityNotApprovedError, match="RiskManager-issued"):
        await executor.execute_opportunity(opportunity)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "target_size"),
    [
        pytest.param(
            lambda opportunity: opportunity.legs.append(
                Leg(
                    "third",
                    "YES",
                    "Third",
                    "market-3",
                    "Third synthetic leg?",
                    0.10,
                    "ask",
                    depth=10,
                )
            ),
            1.0,
            id="legs",
        ),
        pytest.param(
            lambda opportunity: setattr(opportunity.legs[0], "price", 50.0),
            1.0,
            id="prices",
        ),
        pytest.param(
            lambda opportunity: setattr(opportunity, "total_cost", 100.0),
            1.0,
            id="cost",
        ),
        pytest.param(
            lambda opportunity: opportunity.market_ids.append("market-3"),
            1.0,
            id="markets",
        ),
        pytest.param(
            lambda opportunity: setattr(opportunity, "strategy_id", "changed"),
            1.0,
            id="strategy",
        ),
        pytest.param(
            lambda opportunity: setattr(opportunity, "risk_level", RiskLevel.HIGH),
            1.0,
            id="risk",
        ),
        pytest.param(
            lambda opportunity: setattr(opportunity, "liquidity_score", 0.1),
            1.0,
            id="liquidity",
        ),
        pytest.param(None, 0.5, id="size"),
    ],
)
async def test_post_approval_mutations_invalidate_execution(mutation, target_size):
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    executor = BasketExecutor(risk_manager=manager)

    if mutation is not None:
        mutation(opportunity)

    assert manager.has_active_approval(opportunity, target_size) is False
    with pytest.raises(OpportunityNotApprovedError, match="RiskManager-issued"):
        await executor.execute_opportunity(opportunity, target_size=target_size)


@pytest.mark.asyncio
async def test_risk_slippage_tolerance_cancels_leg():
    opportunity = make_opportunity()
    manager = approve_for_simulation(
        opportunity,
        limits=RiskLimits(max_slippage_tolerance=20),
    )
    executor = BasketExecutor(max_slippage_bps=100, risk_manager=manager)

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
    executor = BasketExecutor(execution_mode=ExecutionMode.LIVE)

    with pytest.raises(LiveExecutionDisabledError, match="disabled"):
        await executor.execute_opportunity(opportunity)
    with pytest.raises(LiveExecutionDisabledError, match="disabled"):
        await executor.submit_live_order(opportunity)


@pytest.mark.asyncio
async def test_simulation_is_excluded_from_execution_and_realized_metrics():
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    result = await BasketExecutor(risk_manager=manager).execute_opportunity(opportunity)
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
    manager = approve_for_simulation(opportunity)
    result = await BasketExecutor(risk_manager=manager).execute_opportunity(opportunity)
    tracker = PerformanceTracker()
    tracker.add_execution(opportunity.id, result)
    tracker.calculate_metrics()

    result.execution_mode = ExecutionMode.LIVE
    result.lifecycle_state = LifecycleState.SETTLED
    result.settled_payout = 1.0

    with pytest.raises(UnvalidatedLiveExecutionError, match="no provenance-bearing"):
        tracker.calculate_metrics()


NONFINITE_VALUES = [
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
]


@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    "field_name",
    [
        "max_total_notional",
        "max_per_strategy_notional",
        "max_per_market_notional",
        "max_per_topic_notional",
        "max_positions",
        "max_positions_per_market",
        "min_profit_threshold",
        "max_rule_risk_exposure",
        "max_slippage_tolerance",
        "min_liquidity_score",
    ],
)
def test_risk_limits_reject_every_nonfinite_numeric_limit(field_name, value):
    with pytest.raises(ValueError, match="finite"):
        RiskLimits(**{field_name: value})


@pytest.mark.parametrize("value", NONFINITE_VALUES)
def test_risk_approval_rejects_nonfinite_size_without_reserving(value):
    opportunity = make_opportunity()
    manager = RiskManager()

    passed, violations = manager.approve_opportunity(opportunity, value)

    assert passed is False
    assert any("finite" in violation for violation in violations)
    assert manager.approvals == {}
    assert manager.get_exposure_summary()["total_notional"] == 0.0
    assert opportunity.lifecycle_state == LifecycleState.DETECTED


@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    ("target", "field_name"),
    [
        ("opportunity", "total_cost"),
        ("opportunity", "worst_case_payoff"),
        ("opportunity", "best_case_payoff"),
        ("opportunity", "expected_profit"),
        ("opportunity", "profit_percentage"),
        ("opportunity", "adjusted_cost"),
        ("opportunity", "adjusted_profit"),
        ("opportunity", "adjusted_profit_percentage"),
        ("opportunity", "max_size"),
        ("opportunity", "liquidity_score"),
        ("leg", "price"),
        ("leg", "size"),
        ("leg", "spread_bps"),
        ("leg", "depth"),
    ],
)
def test_risk_approval_rejects_nonfinite_opportunity_inputs(target, field_name, value):
    opportunity = make_opportunity()
    subject = opportunity if target == "opportunity" else opportunity.legs[0]
    setattr(subject, field_name, value)
    manager = RiskManager()

    passed, violations = manager.approve_opportunity(opportunity, 1.0)

    assert passed is False
    assert any("finite" in violation for violation in violations)
    assert manager.approvals == {}
    assert manager.get_exposure_summary()["total_notional"] == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE_VALUES)
async def test_nonfinite_target_size_is_rejected_before_simulation(value):
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)

    with pytest.raises(ValueError, match="target_size must be finite"):
        await BasketExecutor(risk_manager=manager).execute_opportunity(
            opportunity,
            target_size=value,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    "input_name",
    ["simulation_fill_ratios", "simulation_slippage_bps"],
)
async def test_nonfinite_simulation_inputs_are_rejected(input_name, value):
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    kwargs = {input_name: [value, 0.0]}

    with pytest.raises(ValueError, match="must be finite"):
        await BasketExecutor(risk_manager=manager).execute_opportunity(
            opportunity,
            **kwargs,
        )


@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    "field_name",
    ["max_slippage_bps", "min_fill_rate", "execution_timeout"],
)
def test_executor_rejects_nonfinite_limits(field_name, value):
    with pytest.raises(ValueError, match="finite"):
        BasketExecutor(**{field_name: value})


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE_VALUES)
async def test_mutated_nonfinite_executor_limit_is_rejected(value):
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    executor = BasketExecutor(risk_manager=manager)
    executor.max_slippage_bps = value

    with pytest.raises(ValueError, match="max_slippage_bps must be finite"):
        await executor.execute_opportunity(opportunity)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE_VALUES)
async def test_post_approval_nonfinite_mutation_invalidates_execution(value):
    opportunity = make_opportunity()
    manager = approve_for_simulation(opportunity)
    opportunity.legs[0].price = value

    assert manager.has_active_approval(opportunity, 1.0) is False
    with pytest.raises(OpportunityNotApprovedError, match="RiskManager-issued"):
        await BasketExecutor(risk_manager=manager).execute_opportunity(opportunity)


def test_already_expired_opportunity_cannot_be_approved(monkeypatch):
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    opportunity = make_opportunity()
    opportunity.expires_at = now - timedelta(microseconds=1)
    manager = RiskManager()
    monkeypatch.setattr(manager, "_utc_now", lambda: now)

    passed, violations = manager.approve_opportunity(opportunity, 1.0)

    assert passed is False
    assert violations == ["Opportunity has expired"]
    assert manager.approvals == {}
    assert manager.get_exposure_summary()["total_notional"] == 0.0


def test_naive_expiration_timestamp_fails_closed(monkeypatch):
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    opportunity = make_opportunity()
    opportunity.expires_at = datetime(2026, 7, 20, 12, 0)
    manager = RiskManager()
    monkeypatch.setattr(manager, "_utc_now", lambda: now)

    passed, violations = manager.approve_opportunity(opportunity, 1.0)

    assert passed is False
    assert violations == ["expires_at must be a timezone-aware datetime"]
    assert manager.approvals == {}


@pytest.mark.asyncio
async def test_approval_that_expires_before_execution_is_revoked(monkeypatch):
    clock = {"now": datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)}
    opportunity = make_opportunity()
    opportunity.expires_at = clock["now"] + timedelta(minutes=1)
    manager = RiskManager()
    monkeypatch.setattr(manager, "_utc_now", lambda: clock["now"])
    assert manager.approve_opportunity(opportunity, 1.0) == (True, [])
    assert manager.get_exposure_summary()["approved_notional"] == pytest.approx(0.9)

    clock["now"] += timedelta(minutes=2)

    with pytest.raises(OpportunityNotApprovedError, match="RiskManager-issued"):
        await BasketExecutor(risk_manager=manager).execute_opportunity(opportunity)
    assert opportunity.lifecycle_state == LifecycleState.DETECTED
    assert manager.approvals == {}
    assert manager.get_exposure_summary()["approved_notional"] == 0.0
    assert manager.get_exposure_summary()["total_notional"] == 0.0


def test_expired_reservation_no_longer_consumes_aggregate_limit(monkeypatch):
    clock = {"now": datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)}
    first = make_opportunity(opportunity_id="expires-first")
    first.expires_at = (clock["now"] + timedelta(minutes=1)).astimezone(
        timezone(timedelta(hours=-7))
    )
    second = make_opportunity(opportunity_id="second")
    manager = RiskManager(RiskLimits(max_total_notional=0.9))
    monkeypatch.setattr(manager, "_utc_now", lambda: clock["now"])
    assert manager.approve_opportunity(first, 1.0) == (True, [])

    clock["now"] += timedelta(minutes=2)

    assert manager.approve_opportunity(second, 1.0) == (True, [])
    summary = manager.get_exposure_summary()
    assert first.lifecycle_state == LifecycleState.DETECTED
    assert second.lifecycle_state == LifecycleState.APPROVED
    assert summary["approved_notional"] == pytest.approx(0.9)
    assert summary["approved_positions"] == 2
