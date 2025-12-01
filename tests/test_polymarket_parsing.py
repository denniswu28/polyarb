"""Tests for Polymarket parsing behavior."""

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
