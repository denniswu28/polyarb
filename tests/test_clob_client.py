import types

import pytest

from polyarb.data.clob_client import CLOBClient


def test_archived_client_integration_fails_closed():
    with pytest.raises(NotImplementedError, match="archived py-clob-client"):
        CLOBClient(use_py_clob_client=True)


def test_normalize_orderbook_handles_dict_and_lists():
    raw_orderbook = {
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [["0.55", "50"]],
    }

    normalized = CLOBClient._normalize_orderbook(raw_orderbook)

    assert normalized == {
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.55", "size": "50"}],
    }


def test_normalize_orderbook_handles_attribute_payloads():
    payload = types.SimpleNamespace(
        bids=[{"p": "0.4", "s": "20"}],
        asks=[("0.6", "10")],
    )

    normalized = CLOBClient._normalize_orderbook(payload)

    assert normalized == {
        "bids": [{"price": "0.4", "size": "20"}],
        "asks": [{"price": "0.6", "size": "10"}],
    }


def test_normalize_orderbook_maps_buys_and_sells():
    raw_orderbook = {
        "buys": [["0.1", "5"]],
        "sells": [{"price": "0.2", "size": "3"}],
    }

    normalized = CLOBClient._normalize_orderbook(raw_orderbook)

    assert normalized == {
        "bids": [{"price": "0.1", "size": "5"}],
        "asks": [{"price": "0.2", "size": "3"}],
    }


def test_normalize_orderbook_assigns_orders_with_side_hint():
    side_filtered = {"orders": [["0.3", "7"]]}

    normalized = CLOBClient._normalize_orderbook(side_filtered, side="SELL")

    assert normalized == {
        "bids": [],
        "asks": [{"price": "0.3", "size": "7"}],
    }


def test_extract_trade_price_handles_nested_data():
    trades = {"data": {"trades": [{"price": "0.42"}]}}

    assert CLOBClient._extract_trade_price(trades) == 0.42


@pytest.mark.asyncio
async def test_fetch_last_trade_price_uses_public_endpoint():
    calls = []

    class FixtureResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"price": "0.42", "side": "BUY"}

    class FixtureClient:
        async def get(self, url, params):
            calls.append((url, params))
            return FixtureResponse()

        async def aclose(self):
            return None

    client = object.__new__(CLOBClient)
    client.base_url = "https://clob.example.test"
    client._live_price_cache = {}
    client.client = FixtureClient()

    try:
        assert await client.fetch_last_trade_price("token-1") == 0.42
    finally:
        await client.close()

    assert calls == [
        (
            "https://clob.example.test/last-trade-price",
            {"token_id": "token-1"},
        )
    ]
