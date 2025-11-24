"""
Tests for the arbitrage engine core functionality.
"""

import pytest
from polyarb.core.arbitrage_engine import ArbitrageEngine
from polyarb.core.opportunity import ArbitrageOpportunity, OpportunityType
from polyarb.platforms.base import PlatformInterface, Market


class MockPlatform(PlatformInterface):
    """Mock platform for testing."""
    
    def __init__(self, markets=None, name="MockPlatform", **kwargs):
        super().__init__(**kwargs)
        self._markets = markets or []
        self._name = name
    
    @property
    def platform_name(self) -> str:
        return self._name
    
    def get_markets(self, limit=None):
        if limit:
            return self._markets[:limit]
        return self._markets
    
    def get_market(self, market_id):
        for market in self._markets:
            if market.id == market_id:
                return market
        return None


def test_arbitrage_engine_initialization():
    """Test that the arbitrage engine initializes correctly."""
    engine = ArbitrageEngine()
    assert engine is not None
    assert len(engine.platforms) == 0
    assert engine.min_profit_threshold == 1.0


def test_add_platform():
    """Test adding a platform to the engine."""
    engine = ArbitrageEngine()
    platform = MockPlatform()
    
    engine.add_platform(platform)
    assert len(engine.platforms) == 1
    assert platform in engine.platforms


def test_remove_platform():
    """Test removing a platform from the engine."""
    engine = ArbitrageEngine()
    platform = MockPlatform()
    
    engine.add_platform(platform)
    engine.remove_platform(platform)
    assert len(engine.platforms) == 0


def test_intra_platform_arbitrage_detection():
    """Test detection of intra-platform arbitrage opportunities."""
    # Create a market with total price < 1
    market = Market(
        id="test_market_1",
        platform="MockPlatform",
        question="Will it rain?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.45, "No": 0.50}  # Total: 0.95
    )
    
    platform = MockPlatform(markets=[market])
    engine = ArbitrageEngine(
        platforms=[platform],
        min_profit_threshold=0.1  # Low threshold for testing
    )
    
    opportunities = engine.find_opportunities()
    
    assert len(opportunities) > 0
    opp = opportunities[0]
    assert opp.opportunity_type == OpportunityType.INTRA_PLATFORM
    assert opp.profit_percentage > 0


def test_no_arbitrage_when_prices_sum_to_one():
    """Test that no arbitrage is detected when prices sum to 1."""
    market = Market(
        id="test_market_2",
        platform="MockPlatform",
        question="Will it snow?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.50, "No": 0.50}  # Total: 1.00
    )
    
    platform = MockPlatform(markets=[market])
    engine = ArbitrageEngine(platforms=[platform])
    
    opportunities = engine.find_opportunities()
    
    assert len(opportunities) == 0


def test_intra_platform_skips_non_positive_totals():
    """Markets with non-positive total prices should be ignored."""
    market = Market(
        id="invalid_market",
        platform="MockPlatform",
        question="Broken odds?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.0, "No": 0.0},
    )

    platform = MockPlatform(markets=[market])
    engine = ArbitrageEngine(platforms=[platform], min_profit_threshold=0.1)

    opportunities = engine.find_opportunities()

    assert opportunities == []


def test_opportunity_is_profitable():
    """Test the is_profitable method of ArbitrageOpportunity."""
    opp = ArbitrageOpportunity(
        opportunity_type=OpportunityType.INTRA_PLATFORM,
        market_ids=["test"],
        platforms=["MockPlatform"],
        description="Test opportunity",
        profit_percentage=5.0,
        strategy={}
    )
    
    assert opp.is_profitable(min_profit_threshold=1.0) is True
    assert opp.is_profitable(min_profit_threshold=10.0) is False


def test_market_get_price():
    """Test Market.get_price method."""
    market = Market(
        id="test_market_3",
        platform="MockPlatform",
        question="Test question?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.60, "No": 0.40}
    )
    
    assert market.get_price("Yes") == 0.60
    assert market.get_price("No") == 0.40
    assert market.get_price("Maybe") is None


def test_cross_platform_skips_non_positive_prices():
    """Cross-platform analysis should skip non-positive outcome prices."""
    market1 = Market(
        id="market_a",
        platform="Platform1",
        question="Will the thing happen?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.0, "No": 0.5},
    )

    market2 = Market(
        id="market_b",
        platform="Platform2",
        question="Will the thing happen?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.1, "No": 0.5},
    )

    platform1 = MockPlatform(markets=[market1], name="Platform1")
    platform2 = MockPlatform(markets=[market2], name="Platform2")

    engine = ArbitrageEngine(platforms=[platform1, platform2], min_profit_threshold=0.1)

    opportunities = engine.find_opportunities()

    cross_platform_opps = [
        o for o in opportunities
        if o.opportunity_type == OpportunityType.CROSS_PLATFORM
    ]

    assert cross_platform_opps == []


def test_cross_platform_arbitrage_detection():
    """Test detection of cross-platform arbitrage opportunities."""
    # Create two platforms with the same market but different prices
    market1 = Market(
        id="market_1",
        platform="Platform1",
        question="Will candidate X win?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.55, "No": 0.45}
    )
    
    market2 = Market(
        id="market_2",
        platform="Platform2",
        question="Will candidate X win?",  # Same question
        outcomes=["Yes", "No"],
        prices={"Yes": 0.65, "No": 0.35}  # Higher price for Yes
    )
    
    platform1 = MockPlatform(markets=[market1], name="Platform1")
    platform2 = MockPlatform(markets=[market2], name="Platform2")
    
    engine = ArbitrageEngine(
        platforms=[platform1, platform2],
        min_profit_threshold=0.1
    )
    
    opportunities = engine.find_opportunities()
    
    # Should find cross-platform opportunity for price difference
    cross_platform_opps = [
        o for o in opportunities 
        if o.opportunity_type == OpportunityType.CROSS_PLATFORM
    ]
    
    assert len(cross_platform_opps) > 0
