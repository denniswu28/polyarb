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


def test_extract_trade_price_handles_nested_data():
    trades = {"data": {"trades": [{"price": "0.42"}]}}

    assert CLOBClient._extract_trade_price(trades) == 0.42
