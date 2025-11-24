import types

from polyarb.data.clob_client import CLOBClient


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
