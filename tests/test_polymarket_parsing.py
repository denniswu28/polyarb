"""Tests for credential-free Polymarket reference-data parsing."""

import pytest

from polyarb.platforms.polymarket import PolymarketPlatform


def test_parse_market_handles_string_outcomes_with_price_list():
    """Markets with string-only outcomes should parse without errors."""
    platform = PolymarketPlatform()

    raw_market = {
        "id": "test-market",
        "question": "Will it work?",
        "outcomes": ["Yes", "No"],
        "outcomePrices": ["0.55", "0.45"],
    }

    market = platform._parse_market(raw_market)

    assert market.outcomes == ["Yes", "No"]
    assert market.prices == {"Yes": 0.55, "No": 0.45}
    assert market.question == "Will it work?"
    assert market.metadata["price_semantics"] == "reference"
    assert market.metadata["price_source"] == "gamma_display"
    assert market.get_executable_price("Yes", "buy") is None


def test_parse_market_accepts_prices_embedded_in_token_dicts(capsys):
    platform = PolymarketPlatform()
    raw_market = {
        "id": "token-priced",
        "question": "Do token prices parse?",
        "tokens": [
            {"outcome": "Yes", "price": "0.57"},
            {"outcome": "No", "price": "0.43"},
        ],
        "outcomePrices": ["0.10"],
    }

    market = platform._parse_market(raw_market)

    assert market.prices == {"Yes": 0.57, "No": 0.43}
    assert capsys.readouterr().out == ""


def test_public_gamma_adapter_never_accepts_or_sends_api_key():
    platform = PolymarketPlatform()

    assert "Authorization" not in platform.session.headers
    with pytest.raises(ValueError, match="does not accept API credentials"):
        PolymarketPlatform(api_key=object())


def test_get_markets_paginates_events():
    """Pagination should keep requesting pages until exhausted."""

    class FakeResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class PagingSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params))
            offset = params.get("offset", 0)

            pages = {
                0: {"events": [
                    {
                        "id": "event-1",
                        "markets": [
                            {
                                "id": "m1",
                                "question": "Q1?",
                                "active": True,
                                "outcomes": ["Yes", "No"],
                                "outcomePrices": ["0.6", "0.4"],
                            }
                        ],
                    }
                ]},
                1: {"events": [
                    {
                        "id": "event-2",
                        "markets": [
                            {
                                "id": "m2",
                                "question": "Q2?",
                                "active": True,
                                "outcomes": ["Yes", "No"],
                                "outcomePrices": ["0.7", "0.3"],
                            }
                        ],
                    }
                ]},
            }

            data = pages.get(offset, {"events": []})
            return FakeResponse(data)

    platform = PolymarketPlatform()
    platform.session = PagingSession()

    markets = platform.get_markets(limit=None, page_size=1)

    assert [m.id for m in markets] == ["m1", "m2"]
    assert len(platform.session.calls) == 3  # two pages with data, one empty page
