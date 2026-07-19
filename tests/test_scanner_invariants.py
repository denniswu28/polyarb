"""Offline tests for price orientation and scanner arithmetic."""

import pytest

from polyarb.data.models import PriceType
from polyarb.data.price_accessor import PriceAccessor
from polyarb.scanner.base_scanner import BaseScanner
from polyarb.scanner.single_condition_scanner import SingleConditionScanner


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
