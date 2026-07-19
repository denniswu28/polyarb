import json
from pathlib import Path

import pytest

from examples import single_event_multi_market_scan as live_example
from polyarb.scanner.single_event_multi_market_scanner import (
    SingleEventMultiMarketScanner,
)
from polyarb.scanner.enhanced_opportunity import OpportunityClass
from polyarb.data.models import PriceType


class DummyCLOB:
    async def fetch_spread(self, token_id):
        return {"spread_bps": 0, "best_ask_size": 100, "best_bid_size": 100}


class DummyPriceAccessor:
    def __init__(self, prices):
        self.prices = prices
        self.clob_client = DummyCLOB()

    async def get_price(self, token_id, price_type, side="buy"):
        return self.prices.get(token_id)


def test_live_example_parses_current_gamma_string_arrays(monkeypatch):
    fixture_path = Path(__file__).parent / "fixtures" / "gamma_current_schema.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    class FixtureResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    monkeypatch.setattr(live_example.requests, "get", lambda *args, **kwargs: FixtureResponse())

    assert live_example.fetch_markets(limit=1) == [
        {
            "id": "market-current-schema",
            "event_id": "event-current-schema",
            "question": "Will the synthetic condition resolve Yes?",
            "outcomes": [
                {"label": "Yes", "yes_token_id": "token-yes"},
                {"label": "No", "yes_token_id": "token-no"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_multi_market_event_with_other_option():
    prices = {
        "y1": 0.20,
        "y2": 0.20,
        "y3": 0.20,
        "y4": 0.20,
        "y_other": 0.15,
    }
    price_accessor = DummyPriceAccessor(prices)
    scanner = SingleEventMultiMarketScanner(
        price_accessor=price_accessor,
        min_profit_threshold=0.1,
        max_total_price_threshold=0.98,
        price_type=PriceType.ASK,
    )

    markets = [
        {
            "id": "m1",
            "event_id": "event1",
            "question": "Will Barron attend Georgetown?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y1"}],
        },
        {
            "id": "m2",
            "event_id": "event1",
            "question": "Will Barron attend NYU?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y2"}],
        },
        {
            "id": "m3",
            "event_id": "event1",
            "question": "Will Barron attend UPenn?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y3"}],
        },
        {
            "id": "m4",
            "event_id": "event1",
            "question": "Will Barron attend Harvard?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y4"}],
        },
        {
            "id": "m_other",
            "event_id": "event1",
            "question": "Will Barron attend another college?",
            "outcomes": [{"label": "Another college", "yes_token_id": "y_other"}],
        },
    ]

    result = await scanner.scan(markets)

    assert result.get_opportunity_count() == 1
    opportunity = result.opportunities[0]
    assert opportunity.opportunity_class == OpportunityClass.SINGLE_EVENT_MULTI_MARKET
    assert opportunity.total_cost == pytest.approx(0.95)
    assert opportunity.profit_percentage > 0
    assert set(opportunity.market_ids) == {"m1", "m2", "m3", "m4", "m_other"}
    assert opportunity.event_ids == ["event1"]


@pytest.mark.asyncio
async def test_multi_market_event_without_other_option_skips():
    prices = {"y1": 0.3, "y2": 0.3, "y3": 0.3}
    price_accessor = DummyPriceAccessor(prices)
    scanner = SingleEventMultiMarketScanner(price_accessor=price_accessor)

    markets = [
        {
            "id": "m1",
            "event_id": "event1",
            "question": "Will option A happen?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y1"}],
        },
        {
            "id": "m2",
            "event_id": "event1",
            "question": "Will option B happen?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y2"}],
        },
        {
            "id": "m3",
            "event_id": "event1",
            "question": "Will option C happen?",
            "outcomes": [{"label": "Yes", "yes_token_id": "y3"}],
        },
    ]

    result = await scanner.scan(markets)

    assert result.get_opportunity_count() == 0
