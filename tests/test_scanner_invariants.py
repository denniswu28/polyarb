"""Offline tests for price orientation and scanner arithmetic."""

from copy import deepcopy

import pytest

from polyarb.data.models import PriceType
from polyarb.data.price_accessor import PriceAccessor
from polyarb.scanner.base_scanner import BaseScanner
from polyarb.scanner.negrisk_scanner import NegRiskScanner
from polyarb.scanner.single_condition_scanner import SingleConditionScanner
from polyarb.scanner.single_event_multi_market_scanner import (
    SingleEventMultiMarketScanner,
)


NONFINITE_VALUES = [
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
]


class UnsortedCLOB:
    async def fetch_orderbook(self, token_id, side=None):
        del token_id, side
        return {
            "bids": [{"price": "0.40", "size": "2"}, {"price": "0.45", "size": "3"}],
            "asks": [{"price": "0.60", "size": "4"}, {"price": "0.55", "size": "5"}],
        }


class StaticCLOB:
    async def fetch_spread(self, token_id):
        del token_id
        return {"spread_bps": 0.0, "best_ask_size": 25.0, "best_bid_size": 40.0}


class StaticPriceAccessor:
    def __init__(self, prices):
        self.prices = prices
        self.clob_client = StaticCLOB()
        self.calls = []

    async def get_price(self, token_id, price_type, side="buy"):
        self.calls.append((token_id, price_type, side))
        return self.prices.get(token_id)


@pytest.mark.asyncio
async def test_price_accessor_uses_lowest_ask_and_highest_bid():
    accessor = PriceAccessor(UnsortedCLOB())

    assert await accessor.get_price("yes", PriceType.ASK, side="buy") == pytest.approx(0.55)
    assert await accessor.get_price("yes", PriceType.BID, side="sell") == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_price_accessor_rejects_wrong_side_orientation():
    accessor = PriceAccessor(UnsortedCLOB())

    with pytest.raises(ValueError, match="ASK is a buy-side"):
        await accessor.get_price("yes", PriceType.ASK, side="sell")
    with pytest.raises(ValueError, match="BID is a sell-side"):
        await accessor.get_price("yes", PriceType.BID, side="buy")


def test_profit_metrics_apply_fee_and_slippage_inputs():
    scanner = BaseScanner(price_accessor=None)

    metrics = scanner.calculate_profit_metrics(
        total_cost=0.95,
        worst_case_payoff=1.0,
        best_case_payoff=1.0,
        fee_rate_bps=50,
        slippage_bps=50,
    )

    assert metrics["fee_cost"] == pytest.approx(0.00475)
    assert metrics["slippage_cost"] == pytest.approx(0.00475)
    assert metrics["effective_cost"] == pytest.approx(0.9595)
    assert metrics["expected_profit"] == pytest.approx(0.0405)
    assert metrics["profit_percentage"] == pytest.approx(0.0405 / 0.9595 * 100)


def test_profit_metrics_enforce_cost_and_payoff_invariants():
    scanner = BaseScanner(price_accessor=None)

    with pytest.raises(ValueError, match="invariants"):
        scanner.calculate_profit_metrics(-0.1, 1.0, 1.0)
    with pytest.raises(ValueError, match="invariants"):
        scanner.calculate_profit_metrics(0.9, 1.1, 1.0)
    with pytest.raises(ValueError, match="non-negative"):
        scanner.calculate_profit_metrics(0.9, 1.0, 1.0, fee_rate_bps=-1)


@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    "field_name",
    [
        "min_profit_threshold",
        "max_total_price_threshold",
        "fee_rate_bps",
        "slippage_bps",
    ],
)
def test_scanner_rejects_nonfinite_configuration_limits(field_name, value):
    with pytest.raises(ValueError, match="finite"):
        BaseScanner(price_accessor=None, **{field_name: value})


@pytest.mark.parametrize("value", NONFINITE_VALUES)
@pytest.mark.parametrize(
    "field_name",
    [
        "total_cost",
        "worst_case_payoff",
        "best_case_payoff",
        "fee_rate_bps",
        "slippage_bps",
    ],
)
def test_profit_metrics_reject_nonfinite_inputs(field_name, value):
    inputs = {
        "total_cost": 0.9,
        "worst_case_payoff": 1.0,
        "best_case_payoff": 1.0,
        "fee_rate_bps": 0.0,
        "slippage_bps": 0.0,
    }
    inputs[field_name] = value

    with pytest.raises(ValueError, match="finite"):
        BaseScanner(price_accessor=None).calculate_profit_metrics(**inputs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "price_type",
    [PriceType.BID, PriceType.MID, PriceType.LIVE, PriceType.ACTUAL],
)
async def test_long_only_scanner_rejects_non_ask_reference_costs(price_type):
    accessor = StaticPriceAccessor({"yes": 0.4, "no": 0.5})
    scanner = SingleConditionScanner(price_accessor=accessor)

    with pytest.raises(ValueError, match="require ASK prices"):
        await scanner.scan([], price_type=price_type)
    assert accessor.calls == []


@pytest.mark.asyncio
async def test_yes_no_outcome_orientation_and_ask_liquidity():
    accessor = StaticPriceAccessor({"yes-token": 0.45, "no-token": 0.50})
    scanner = SingleConditionScanner(
        price_accessor=accessor,
        min_profit_threshold=0.1,
        max_total_price_threshold=0.98,
    )
    market = {
        "id": "binary",
        "question": "Synthetic outcome?",
        "outcomes": [
            {"label": "No", "no_token_id": "no-token"},
            {"label": "Yes", "yes_token_id": "yes-token"},
        ],
    }

    result = await scanner.scan([market])

    assert result.get_opportunity_count() == 1
    opportunity = result.opportunities[0]
    assert [(leg.side, leg.token_id) for leg in opportunity.legs] == [
        ("YES", "yes-token"),
        ("NO", "no-token"),
    ]
    assert all(leg.price_type == PriceType.ASK.value for leg in opportunity.legs)
    assert opportunity.max_size == pytest.approx(25.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NONFINITE_VALUES)
async def test_single_condition_scanner_rejects_nonfinite_ask(value):
    accessor = StaticPriceAccessor({"yes-token": value, "no-token": 0.50})
    scanner = SingleConditionScanner(price_accessor=accessor)
    market = {
        "id": "binary",
        "question": "Synthetic outcome?",
        "outcomes": [
            {"label": "Yes", "yes_token_id": "yes-token"},
            {"label": "No", "no_token_id": "no-token"},
        ],
    }

    result = await scanner.scan([market])

    assert result.get_opportunity_count() == 0


def make_coverage_group():
    return [
        {
            "id": "market-a",
            "event_id": "event-1",
            "question": "Will option A occur?",
            "outcomes": [{"label": "Yes", "yes_token_id": "token-a"}],
            "is_neg_risk": True,
            "neg_risk_id": "neg-risk-1",
        },
        {
            "id": "market-b",
            "event_id": "event-1",
            "question": "Will option B occur?",
            "outcomes": [{"label": "Yes", "yes_token_id": "token-b"}],
            "is_neg_risk": True,
            "neg_risk_id": "neg-risk-1",
        },
        {
            "id": "market-other",
            "event_id": "event-1",
            "question": "Will another option occur?",
            "outcomes": [{"label": "Yes", "yes_token_id": "token-other"}],
            "is_neg_risk": True,
            "neg_risk_id": "neg-risk-1",
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scanner_class",
    [SingleEventMultiMarketScanner, NegRiskScanner],
)
@pytest.mark.parametrize("missing_input", ["outcome", "token", "ask"])
async def test_coverage_scanners_reject_entire_group_when_a_required_leg_is_missing(
    scanner_class,
    missing_input,
):
    complete_prices = {
        "token-a": 0.20,
        "token-b": 0.20,
        "token-other": 0.20,
    }
    scanner = scanner_class(
        price_accessor=StaticPriceAccessor(dict(complete_prices)),
        min_profit_threshold=0.1,
        max_total_price_threshold=0.98,
        price_type=PriceType.ASK,
    )

    complete = await scanner.scan(make_coverage_group())
    assert complete.get_opportunity_count() == 1

    incomplete_markets = deepcopy(make_coverage_group())
    incomplete_prices = dict(complete_prices)
    if missing_input == "outcome":
        incomplete_markets[1]["outcomes"] = []
    elif missing_input == "token":
        incomplete_markets[1]["outcomes"][0].pop("yes_token_id")
    else:
        incomplete_prices.pop("token-b")

    scanner.price_accessor = StaticPriceAccessor(incomplete_prices)
    incomplete = await scanner.scan(incomplete_markets)

    assert incomplete.get_opportunity_count() == 0
