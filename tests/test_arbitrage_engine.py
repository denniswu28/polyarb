"""
Tests for the arbitrage engine core functionality.
"""

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


def executable_quotes(asks, bids=None):
    """Build explicit synthetic order-book metadata for engine tests."""
    return {
        "price_semantics": "executable",
        "asks": dict(asks),
        "bids": dict(bids if bids is not None else asks),
    }


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
        prices={"Yes": 0.45, "No": 0.50},
        metadata=executable_quotes({"Yes": 0.45, "No": 0.50}),
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


def test_reference_display_prices_are_not_executable_inputs():
    market = Market(
        id="reference-only",
        platform="MockPlatform",
        question="Reference-only display market?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.40, "No": 0.40},
        metadata={
            "price_semantics": "reference",
            "price_source": "gamma_display",
        },
    )
    platform = MockPlatform(markets=[market])

    assert ArbitrageEngine(platforms=[platform], min_profit_threshold=0).find_opportunities() == []


def test_intra_platform_cost_inputs_can_remove_a_gross_candidate():
    market = Market(
        id="cost-sensitive",
        platform="MockPlatform",
        question="Cost-sensitive synthetic market?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.49, "No": 0.49},
        metadata=executable_quotes({"Yes": 0.49, "No": 0.49}),
    )
    platform = MockPlatform(markets=[market])
    engine = ArbitrageEngine(
        platforms=[platform],
        min_profit_threshold=0.0,
        max_total_price_threshold=0.99,
        fee_rate_bps=100,
        slippage_bps=100,
    )

    assert engine.find_opportunities() == []


def test_no_arbitrage_when_prices_sum_to_one():
    """Test that no arbitrage is detected when prices sum to 1."""
    market = Market(
        id="test_market_2",
        platform="MockPlatform",
        question="Will it snow?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.50, "No": 0.50},
        metadata=executable_quotes({"Yes": 0.50, "No": 0.50}),
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
        metadata=executable_quotes({"Yes": 0.0, "No": 0.0}),
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
        metadata=executable_quotes({"Yes": 0.0, "No": 0.5}),
    )

    market2 = Market(
        id="market_b",
        platform="Platform2",
        question="Will the thing happen?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.1, "No": 0.5},
        metadata=executable_quotes({"Yes": 0.1, "No": 0.5}),
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
        prices={"Yes": 0.55, "No": 0.45},
        metadata=executable_quotes(
            {"Yes": 0.56, "No": 0.46},
            {"Yes": 0.54, "No": 0.44},
        ),
    )
    
    market2 = Market(
        id="market_2",
        platform="Platform2",
        question="Will candidate X win?",  # Same question
        outcomes=["Yes", "No"],
        prices={"Yes": 0.65, "No": 0.35},
        metadata=executable_quotes(
            {"Yes": 0.66, "No": 0.36},
            {"Yes": 0.64, "No": 0.34},
        ),
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
    yes_candidate = next(
        candidate
        for candidate in cross_platform_opps
        if candidate.strategy["outcome"] == "Yes"
    )
    assert yes_candidate.strategy["buy_price"] == 0.56
    assert yes_candidate.strategy["sell_price"] == 0.64
    assert yes_candidate.strategy["buy_price_semantics"] == "executable_ask"
    assert yes_candidate.strategy["sell_price_semantics"] == "executable_bid"


def test_cross_platform_candidate_order_is_deterministic():
    markets = [
        Market(
            id="market_1",
            platform="Platform1",
            question="Same synthetic event?",
            outcomes=["Yes", "No"],
            prices={"Yes": 0.60, "No": 0.40},
            metadata=executable_quotes(
                {"Yes": 0.61, "No": 0.41},
                {"Yes": 0.59, "No": 0.39},
            ),
        ),
        Market(
            id="market_2",
            platform="Platform2",
            question="Same synthetic event?",
            outcomes=["No", "Yes"],
            prices={"No": 0.30, "Yes": 0.70},
            metadata=executable_quotes(
                {"No": 0.31, "Yes": 0.71},
                {"No": 0.29, "Yes": 0.69},
            ),
        ),
    ]
    engine = ArbitrageEngine(min_profit_threshold=0.0)

    candidates = engine._analyze_cross_platform_market_group(markets)

    assert [candidate.strategy["outcome"] for candidate in candidates] == ["No", "Yes"]
